import argparse
import math
from typing import Any

import requests

API_TIMEOUT = (10, 300)


def request_api(
    api_url: str,
    endpoint: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/{endpoint.lstrip('/')}",
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        detail = response.text if response is not None else str(exc)
        status = response.status_code if response is not None else "?"
        raise RuntimeError(f"API trả về HTTP {status}: {detail}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Không thể gọi API: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("API không trả về JSON hợp lệ.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("API phải trả về một JSON object.")
    return result


def _validate_vector(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"API không trả về vector embedding hợp lệ cho {label}.")
    if any(
        isinstance(component, bool)
        or not isinstance(component, (int, float))
        or not math.isfinite(component)
        for component in value
    ):
        raise RuntimeError(f"Vector embedding của {label} chứa giá trị không hợp lệ.")
    return [float(component) for component in value]


def embedding_cosine_score(
    api_url: str,
    first_sentence: str,
    second_sentence: str,
    model: str | None = None,
) -> tuple[float, str]:
    payload: dict[str, Any] = {
        "texts": [first_sentence, second_sentence],
        "normalize": True,
    }
    if model:
        payload["model"] = model

    result = request_api(api_url, "/embeddings", payload)
    embeddings = result.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != 2:
        raise RuntimeError("Embedding API không trả về đúng hai vector.")

    first_vector = _validate_vector(embeddings[0], "câu thứ nhất")
    second_vector = _validate_vector(embeddings[1], "câu thứ hai")
    if len(first_vector) != len(second_vector):
        raise RuntimeError("Hai vector embedding không cùng số chiều.")

    first_norm = math.sqrt(math.fsum(value * value for value in first_vector))
    second_norm = math.sqrt(math.fsum(value * value for value in second_vector))
    if first_norm == 0 or second_norm == 0:
        raise RuntimeError("Không thể tính cosine similarity với vector zero.")

    dot_product = math.fsum(
        first_value * second_value
        for first_value, second_value in zip(first_vector, second_vector)
    )
    return dot_product / (first_norm * second_norm), str(
        result.get("model", "model không xác định")
    )


def cross_encoder_score(
    api_url: str,
    first_sentence: str,
    second_sentence: str,
) -> float:
    result = request_api(
        api_url,
        "/ranking",
        {
            "query": first_sentence,
            "documents": [{"text": second_sentence, "metadata": {}}],
            "pre_rerank_count": 1,
            "result_count": 1,
        },
    )
    ranked_results = result.get("results")
    if not isinstance(ranked_results, list) or not ranked_results:
        raise RuntimeError("Ranking API không trả về kết quả Cross-Encoder.")

    score = ranked_results[0].get("cross_encoder_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise RuntimeError("Ranking API không trả về điểm Cross-Encoder hợp lệ.")
    if not math.isfinite(score):
        raise RuntimeError("Điểm Cross-Encoder không phải là số hữu hạn.")
    return float(score)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="So sánh hai câu bằng embedding cosine và Cross-Encoder qua API."
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="URL gốc của API (mặc định: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--model",
        help="Model embedding; nếu bỏ qua sẽ dùng model mặc định của API.",
    )
    args = parser.parse_args()

    print("Nhập hai câu để so sánh. Để trống câu thứ nhất để thoát.")
    while True:
        try:
            first_sentence = input("\nCâu thứ nhất: ").strip()
        except EOFError:
            print()
            return 0
        if not first_sentence:
            return 0

        try:
            second_sentence = input("Câu thứ hai: ").strip()
        except EOFError:
            print()
            return 0
        if not second_sentence:
            print("Câu thứ hai không được để trống.")
            continue

        try:
            embedding_score, embedding_model = embedding_cosine_score(
                args.api_url,
                first_sentence,
                second_sentence,
                model=args.model,
            )
            reranker_score = cross_encoder_score(
                args.api_url,
                first_sentence,
                second_sentence,
            )
        except RuntimeError as exc:
            print(f"Lỗi: {exc}")
            continue

        print(f"Embedding cosine ({embedding_model}): {embedding_score:.4f}")
        print(
            "Cross-Encoder raw score "
            f"(câu 1 → câu 2, điểm cao hơn nghĩa là liên quan hơn): {reranker_score:.4f}"
        )
        print("Lưu ý: hai loại điểm có thang đo khác nhau, không so sánh trực tiếp.")


if __name__ == "__main__":
    raise SystemExit(main())
