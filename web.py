import os
import pathlib
import uuid
import re
import time
import requests
from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Azure SDK
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.core.credentials import AzureKeyCredential
from msrest.authentication import CognitiveServicesCredentials
from azure.ai.formrecognizer import DocumentAnalysisClient
import azure.cognitiveservices.speech as speechsdk

# .env 設定
env_path = pathlib.Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# Azure 金鑰與端點
VISION_KEY = os.getenv("VISION_KEY")
VISION_ENDPOINT = os.getenv("VISION_ENDPOINT")
AZURE_MAPS_KEY = os.getenv("AZURE_MAPS_KEY")
SPEECH_KEY = os.getenv("SPEECH_KEY")
SPEECH_REGION = os.getenv("SPEECH_REGION")
TRANSLATOR_KEY = os.getenv("TRANSLATOR_KEY")
TRANSLATOR_REGION = os.getenv("TRANSLATOR_REGION")
TRANSLATOR_ENDPOINT = os.getenv("TRANSLATOR_ENDPOINT")
DOC_KEY = os.getenv("DOC_INTELLIGENCE_KEY")
DOC_ENDPOINT = os.getenv("DOC_INTELLIGENCE_ENDPOINT")

# Flask 應用設定
app = Flask(__name__)
app.secret_key = os.urandom(12)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Azure 客戶端初始化
cv_client = ComputerVisionClient(VISION_ENDPOINT, CognitiveServicesCredentials(VISION_KEY))

# 過敏原關鍵字
ALLERGENS = [
    "milk", "egg", "peanut", "soy", "wheat", "gluten", "shellfish", "shrimp", "crab",
    "tree nut", "almond", "cashew", "pistachio", "芝麻", "花生", "蛋", "奶", "大豆",
    "小麥", "麩質", "甲殼類", "堅果"
]
ALLERGEN_PATTERN = re.compile("|".join([re.escape(a) for a in ALLERGENS]), re.I)

# 翻譯（REST API）
def translate_text(text, dst_lang="zh-Hant"):
    url = f"{TRANSLATOR_ENDPOINT}/translate?api-version=3.0&to={dst_lang}"
    headers = {
        'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': TRANSLATOR_REGION,
        'Content-Type': 'application/json'
    }
    body = [{'text': text}]
    response = requests.post(url, headers=headers, json=body)
    return response.json()[0]['translations'][0]['text']

# 語音合成
def text_to_speech(text, voice="zh-TW-HsiaoChenNeural"):
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    file_name = f"{uuid.uuid4()}.mp3"
    audio_path = os.path.join("static", "audio", file_name)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_path)
    speech_config.speech_synthesis_voice_name = voice
    synthesizer = speechsdk.SpeechSynthesizer(speech_config, audio_config)
    synthesizer.speak_text_async(text).get()
    return file_name

# 首頁
@app.route("/")
def index():
    return render_template("index.html")

# 功能：圖片翻譯與語音
@app.route("/image", methods=["GET", "POST"])
def image():
    image_url = ""
    description = ""
    translation = ""
    audio_file = ""

    if request.method == "POST":
        image_url = request.form.get("image_url")
        client = ComputerVisionClient(VISION_ENDPOINT, CognitiveServicesCredentials(VISION_KEY))
        result = client.describe_image(image_url, max_descriptions=1)
        if result.captions:
            text = result.captions[0].text
            confidence = result.captions[0].confidence
            description = f"{text} [{confidence:.2f}]"
            translation = translate_text(text)
            audio_file = text_to_speech(translation)

    return render_template("image.html", image_url=image_url, description=description, translation=translation, audio_file=audio_file)

# 功能：PDF 摘要
@app.route("/pdf", methods=["GET", "POST"])
def pdf():
    pdf_summary = ""
    if request.method == "POST" and "pdf_file" in request.files:
        pdf_file = request.files["pdf_file"]
        if pdf_file.filename:
            client = DocumentAnalysisClient(DOC_ENDPOINT, AzureKeyCredential(DOC_KEY))
            poller = client.begin_analyze_document("prebuilt-read", document=pdf_file.read())
            result = poller.result()
            all_text = " ".join([line.content for page in result.pages for line in page.lines])
            pdf_summary = all_text[:1000] + ("..." if len(all_text) > 1000 else "")
    return render_template("pdf.html", pdf_summary=pdf_summary)

# 功能：OCR 地圖定位
@app.route("/ocr_map_tool", methods=["GET", "POST"])
def ocr_map_tool():
    extracted_text = ""
    filename = ""
    map_coords = None
    query_address = ""

    if request.method == "POST":
        if "image_file" in request.files:
            file = request.files["image_file"]
            if file.filename != "":
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                with open(file_path, "rb") as f:
                    image_data = f.read()

                try:
                    headers = {
                        "Ocp-Apim-Subscription-Key": VISION_KEY,
                        "Content-Type": "application/octet-stream"
                    }
                    params = {"api-version": "2023-10-01"}
                    ocr_url = f"{VISION_ENDPOINT}/computervision/imageanalysis:analyze?features=read"
                    response = requests.post(ocr_url, headers=headers, params=params, data=image_data)
                    result = response.json()

                    lines = []
                    read_result = result.get("readResult")
                    if read_result and "blocks" in read_result:
                        blocks = read_result["blocks"]
                        for block in blocks:
                            for line in block.get("lines", []):
                                lines.append(line.get("text", ""))
                        extracted_text = "\n".join(lines) if lines else "⚠️ 沒有偵測到文字"
                        if not query_address and len(lines) > 0:
                            query_address = lines[0]
                except Exception as e:
                    extracted_text = f"⚠️ 文字擷取失敗：{str(e)}"

        if request.form.get("map_search") or query_address:
            if not query_address:
                query_address = request.form.get("address", "")
            if query_address:
                try:
                    maps_url = "https://atlas.microsoft.com/search/address/json"
                    maps_params = {
                        "api-version": "1.0",
                        "subscription-key": AZURE_MAPS_KEY,
                        "query": query_address
                    }
                    maps_resp = requests.get(maps_url, params=maps_params)
                    maps_data = maps_resp.json()

                    position = maps_data.get("results", [{}])[0].get("position", {})
                    if position and "lat" in position and "lon" in position:
                        map_coords = {
                            "lat": position.get("lat"),
                            "lon": position.get("lon")
                        }
                except Exception as e:
                    extracted_text += f"\n⚠️ 查詢地圖錯誤：{e}"

    return render_template(
        "ocr_map_tool.html",
        text=extracted_text,
        filename=filename,
        map_coords=map_coords,
        query_address=query_address,
        azure_maps_key=AZURE_MAPS_KEY
    )

# 功能：智慧菜單分析
@app.route("/menu", methods=["GET", "POST"])
def menu_analyzer():
    original_text = translated_text = ""
    allergens = []
    audio_file = ""

    if request.method == "POST":
        if "image" not in request.files or request.files["image"].filename == "":
            flash("請選擇菜單圖片！")
            return redirect(url_for("menu_analyzer"))

        file = request.files["image"]
        uploads_dir = pathlib.Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        img_path = uploads_dir / f"{uuid.uuid4()}.jpg"
        file.save(img_path)

        with open(img_path, "rb") as img_stream:
            read_op = cv_client.read_in_stream(img_stream, raw=True)
        op_id = read_op.headers["Operation-Location"].split("/")[-1]
        result = cv_client.get_read_result(op_id)
        while result.status not in ["succeeded", "failed"]:
            time.sleep(0.3)
            result = cv_client.get_read_result(op_id)

        if result.status == "succeeded":
            original_text = "\n".join(
                line.text
                for page in result.analyze_result.read_results
                for line in page.lines
            )

        translated_text = translate_text(original_text)
        allergens = sorted(set(m.group(0).lower() for m in ALLERGEN_PATTERN.finditer(original_text)))
        audio_file = text_to_speech(translated_text)

        os.remove(img_path)

    return render_template(
        "menu.html",
        original_text=original_text,
        translated_text=translated_text,
        allergens=allergens,
        audio_file=audio_file,
    )

# 執行入口
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
