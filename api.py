"""
    Azure AI 電腦視覺(API 版)
"""
import os
import pathlib
from dotenv import load_dotenv
from flask import Flask, request
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials

# 如果.env存在，讀取.env檔案
env_path = pathlib.Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# 取得環境變數
KEY = os.getenv('KEY')
ENDPOINT = os.getenv('ENDPOINT')

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def object_detection():
    """
        image: 影像 URL
        language: 描述語言
    """
    image = request.args.get('image')
    language = request.args.get('language')

    if image and language:
        client = ComputerVisionClient(
            endpoint=ENDPOINT,
            credentials=CognitiveServicesCredentials(KEY)
        )

        analysis = client.describe_image(url=image, max_descriptions=1, language=language)
        result = analysis.captions[0]
        return f"{result.text} [{result.confidence}]"

    return "Please provide image and language parameters."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
