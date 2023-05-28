from PIL import Image
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
key = Fernet.generate_key()
cipher_suite = Fernet(key)


def hide_text(image_path, text):
    image = Image.open(image_path).convert("RGB")
    pixels = image.load()

    text = cipher_suite.encrypt(text.encode())

    width, height = image.size
    max_bytes = (width * height * 3) // 8

    if len(text) > max_bytes:
        raise ValueError("Text is too large to hide in the image.")

    binary_text = "".join(format(byte, "08b") for byte in text)
    binary_text += "0" * ((width * height * 3) - len(binary_text))

    index = 0
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]

            r = (r & 0xFE) | int(binary_text[index])
            index += 1
            if index >= len(binary_text):
                break

            g = (g & 0xFE) | int(binary_text[index])
            index += 1
            if index >= len(binary_text):
                break

            b = (b & 0xFE) | int(binary_text[index])
            index += 1
            if index >= len(binary_text):
                break

            pixels[x, y] = (r, g, b)

    output_image_path = "hidden_image.png"
    image.save(output_image_path)
    return output_image_path


def read_text(image_path):
    image = Image.open(image_path).convert("RGB")
    pixels = image.load()

    width, height = image.size

    binary_text = ""
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            binary_text += str(r & 1)
            binary_text += str(g & 1)
            binary_text += str(b & 1)

    text_bytes = [binary_text[i:i+8] for i in range(0, len(binary_text), 8)]
    text = "".join(chr(int(byte, 2)) for byte in text_bytes)
    return cipher_suite.decrypt(text.encode()).decode()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/hide")
async def hide(request: Request):
    form = await request.form()
    image_file = form["image"]
    text = form["text"]

    image_path = f"static/{image_file.filename}"
    with open(image_path, "wb") as f:
        f.write(image_file.file.read())

    try:
        output_image_path = hide_text(image_path, text)
    except ValueError as e:
        return {"error": str(e)}

    return templates.TemplateResponse("index.html", {"request": request, "output_path": output_image_path})


@app.post("/read")
async def read(request: Request):
    form = await request.form()
    image_file = form["image"]

    image_path = f"static/{image_file.filename}"
    with open(image_path, "wb") as f:
        f.write(image_file.file.read())

    try:
        text = read_text(image_path)
    except Exception as e:
        return {"error": str(e)}

    return templates.TemplateResponse("index.html", {"request": request, "extracted_text": text})
