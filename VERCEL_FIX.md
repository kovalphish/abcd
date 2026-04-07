# ✅ Исправление для загрузки картинок на Vercel

Vercel НЕ ПОЗВОЛЯЕТ записывать файлы на диск. Все загруженные картинки автоматически удаляются после каждого запроса.

## ✅ Решение: Использовать Cloudinary (БЕСПЛАТНО)

### Шаг 1: Зарегистрируйтесь на cloudinary.com
Это бесплатный сервис для хранения картинок.

### Шаг 2: Установите библиотеку
```
pip install cloudinary
```

### Шаг 3: Добавьте в requirements.txt
```
cloudinary==1.37.0
```

### Шаг 4: Добавьте эти переменные окружения в настройках Vercel:
```
CLOUDINARY_CLOUD_NAME=ваш_cloud_name
CLOUDINARY_API_KEY=ваш_api_key
CLOUDINARY_API_SECRET=ваш_api_secret
```

### Шаг 5: Замените код загрузки картинок на этот:

```python
import cloudinary
import cloudinary.uploader

# Инициализация Cloudinary
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
  secure = True
)

# При загрузке картинки вместо image.save() используйте:
upload_result = cloudinary.uploader.upload(image)
image_filename = upload_result['secure_url']
```

✅ Теперь все картинки будут сохраняться в облаке и работать на Vercel постоянно.

---

### ❗ Альтернатива если не хотите Cloudinary:
Загружайте картинки **только локально**, потом закидывайте их в папку `static/images/` и делайте `git push`. Тогда они попадут в сборку Vercel и будут работать навсегда.

В этом случае в админке при добавлении товара просто указывайте имя файла вместо загрузки.