"""
    Azure AI 電腦視覺(單機版)
"""
import os
import pathlib
from dotenv import load_dotenv
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials

# 如果.env存在，讀取.env檔案
env_path = pathlib.Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# 取得環境變數
KEY = os.getenv('KEY')
ENDPOINT = os.getenv('ENDPOINT')

# Azure 電腦視覺參數
# 影像 URL
IMAGE = 'https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg'
# 描述語言
LANG = 'en'
# 產生的最大描述數量
MAX = 1

client = ComputerVisionClient(
    endpoint=ENDPOINT,
    credentials=CognitiveServicesCredentials(KEY)
)

analysis = client.describe_image(url=IMAGE, max_descriptions=MAX, language=LANG)

for caption in analysis.captions:
    print(caption.text)
    print(caption.confidence)
