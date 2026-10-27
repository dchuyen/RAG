import argparse
import json
import sys
import requests

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL = "intfloat/multilingual-e5-small"

SAMPLE_TEXTS = [
    "Hà Nội là thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.",
    "Trí tuệ nhân tạo đang làm thay đổi toàn diện ngành công nghệ thông tin.",
    "Mô hình ngôn ngữ lớn và kỹ thuật RAG giúp tìm kiếm thông tin chính xác hơn.",
]


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra endpoint embedding tiếng Việt.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Địa chỉ API FastAPI")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model HuggingFace")
    parser.add_argument("--single", action="store_true", help="Dùng GET /embeddings/single thay vì POST /embeddings")
    parser.add_argument("text", nargs="?", default=None, help="Văn bản tuỳ chọn để embed")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")

    if args.single or args.text:
        text = args.text or SAMPLE_TEXTS[0]
        url = f"{api_url}/embeddings/single"
        print(f"-> Gửi yêu cầu GET tới {url}")
        print(f"-> Nội dung: {text}")
        response = requests.get(url, params={"text": text, "model": args.model})
        if response.status_code != 200:
            print(f"Lỗi HTTP {response.status_code}: {response.text}")
            sys.exit(1)
        data = response.json()
        print(f"-> Model: {data.get('model')}")
        print(f"-> Số chiều (dimension): {data.get('dimension')}")
        print(f"-> Vector mẫu (5 phần tử đầu): {data.get('embedding', [])[:5]}...")
    else:
        url = f"{api_url}/embeddings"
        payload = {
            "texts": SAMPLE_TEXTS,
            "model": args.model,
            "normalize": True,
        }
        print(f"-> Gửi yêu cầu POST tới {url}")
        print(f"-> Số lượng câu gửi đi: {len(SAMPLE_TEXTS)}")
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Lỗi HTTP {response.status_code}: {response.text}")
            sys.exit(1)
        data = response.json()
        print(f"-> Model: {data.get('model')}")
        print(f"-> Số chiều (dimension): {data.get('dimension')}")
        print(f"-> Số lượng embeddings trả về: {data.get('count')}")
        for idx, emb in enumerate(data.get("embeddings", [])):
            print(f"   [Câu {idx+1}] Vector (5 phần tử đầu): {emb[:5]}... (độ dài: {len(emb)})")


if __name__ == "__main__":
    main()
