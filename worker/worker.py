import logging
import cv2
import numpy as np
import redis
import json
import tensorflow as tf
import base64
import asyncio
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
from sqlalchemy.exc import IntegrityError

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Настройка базы данных
DATABASE_URI = "postgresql://postgres:postgres@postgres:5432/database"
engine = create_engine(DATABASE_URI)
Base = declarative_base()

class ImageData(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    unique_name_image = Column(String, unique=True, nullable=False)
    blob_image = Column(LargeBinary, nullable=False)
    category_type = Column(Integer, nullable=False)

try:
    Base.metadata.create_all(engine)
    logging.info('Таблица "images" успешно создана или уже существует.')
except IntegrityError as e:
    logging.error(f"Ошибка при создании таблицы: {e}")

Session = sessionmaker(bind=engine)

# Настройка Redis
redis_client = redis.StrictRedis(host="redis", port=6379, db=0, decode_responses=True)

# Загрузка модели
logging.info("Загрузка модели ...")
model = tf.keras.models.load_model("models/anomaly_detection_model.h5")
logging.info("Модель загружена")

# Преобразование кадра
def preprocess_frame(frame):
    resized_frame = cv2.resize(frame, (64, 64))
    normalized_frame = resized_frame.astype(np.float32) / 255.0
    input_frame = np.expand_dims(normalized_frame, axis=0)
    return input_frame

# Асинхронная обработка кадров
async def process_frames():
    session = Session()
    redis_client.expire("success_images", 30)
    while True:
        frame_data = redis_client.brpop("frame_queue", timeout=0)
        if frame_data:
            frame_json = frame_data[1]
            frame_info = json.loads(frame_json)

            frame_array = np.frombuffer(base64.b64decode(frame_info["data"]), np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            processed_frame = preprocess_frame(frame)
            prediction = model.predict(processed_frame)
            predicted_class = np.argmax(prediction)

            logging.info(f"Предсказанный класс: {predicted_class}")

            _, buffer = cv2.imencode(".jpg", frame)
            unique_name = f"{uuid.uuid4()}.jpg"

            new_image_data = ImageData(
                unique_name_image=unique_name,
                blob_image=buffer.tobytes(),
                category_type=int(predicted_class),
            )
            session.add(new_image_data)
            session.commit()
            redis_client.publish("success_images", json.dumps({
                    "id": new_image_data.id,
                    "unique_name_image": new_image_data.unique_name_image,
                    "category_type": new_image_data.category_type,
                    "date": new_image_data.date.isoformat(),
                    "image": frame_info["data"],
                }))
            logging.info("Send frame to redis")

        await asyncio.sleep(0.1)

# Основная функция для запуска обработки кадров
async def main():
    await process_frames()

if __name__ == "__main__":
    logging.info("Запуск асинхронной обработки кадров.")
    asyncio.run(main())
