import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from PIL import Image, ImageGrab

print('📱 二维码/条码识别')
print('截全屏搜索二维码...')
time.sleep(1)

img = ImageGrab.grab()

try:
    from pyzbar.pyzbar import decode as qr_decode, ZBarSymbol
except ImportError:
    print('❌ 需要安装 pyzbar: pip install pyzbar')
    sys.exit(1)

seen = set()
results = []
for scale in [1.0, 0.7]:
    if scale != 1.0:
        w, h = img.size
        scaled = img.resize((int(w * scale), int(h * scale)))
    else:
        scaled = img
    for qr in qr_decode(scaled, symbols=[ZBarSymbol.QRCODE]):
        data = qr.data.decode('utf-8', errors='replace')
        key = data[:50]
        if key not in seen:
            seen.add(key)
            results.append((qr.type, data, qr.rect))

if results:
    print()
    for t, data, rect in results:
        print(f'  [{t}] {data}')
        print(f'  位置: ({rect.x},{rect.y}) {rect.width}x{rect.height} px')
        print()
else:
    print()
    print('❌ 未识别到二维码')
    print('确保屏幕上有清晰的二维码图案')
