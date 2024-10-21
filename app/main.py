import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import cv2
import numpy as np
import base64
import asyncio
import websockets
from enum import Enum
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# Enum для типов преступлений
class CrimeType(Enum):
    ABUSE = 0
    ARREST = 1
    ARSON = 2
    ASSAULT = 3
    BURGLARY = 4
    EXPLOSION = 5
    FIGHTING = 6
    NORMAL = 7
    ROAD_ACCIDENTS = 8
    ROBBERY = 9
    SHOOTING = 10
    SHOPLIFTING = 11
    STEALING = 12
    VANDALISM = 13

    @classmethod
    def get(cls, value):
        """Возвращает описание типа преступления на основе значения."""
        for crime in cls:
            if crime.value == value:
                return crime.name.replace("_", " ").title()
        return None

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

Session = sessionmaker(bind=engine)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка Redis
redis_client = redis.StrictRedis(host="redis", port=6379, db=0, decode_responses=True)

# Набор подключенных клиентов
connected_clients = set()

# Асинхронная отправка списка изображений через WebSocket
@app.websocket("/ws/images")
async def websocket_images_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logging.info(f"Клиент {websocket.client.host} подключен.")

    try:
        # Запрос начального списка изображений
        message = await websocket.receive_text()
        logging.info(f"Запрос от клиента {websocket.client.host}: {message}")
        
        request = json.loads(message)  # Пытаемся разобрать запрос

        # Обработка начального запроса
        if "action" in request and request["action"] == "get_images":
            page = request.get("page", 1)
            per_page = request.get("per_page", 12)
            session = Session()
            total_images = session.query(ImageData).count()
            images = (
                session.query(ImageData)
                .order_by(ImageData.date.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            image_list = []
            for image in images:
                image_blob_base64 = base64.b64encode(image.blob_image).decode("utf-8")
                image_list.append(
                    {
                        "id": image.id,
                        "unique_name_image": image.unique_name_image,
                        "category_type": CrimeType.get(image.category_type),
                        "date": image.date.isoformat(),
                        "image": image_blob_base64,
                    }
                )

            response = {
                "total": total_images,
                "page": page,
                "per_page": per_page,
                "images": image_list,
            }
            await websocket.send_json(response)

        # Подписка на новые изображения через Redis Pub/Sub
        pubsub = redis_client.pubsub()
        pubsub.subscribe("success_images")

        # Цикл получения новых изображений
        while True:
            message = pubsub.get_message()
            if message and message['type'] == 'message':
                new_image_message = json.loads(message["data"])
                logging.info(f"Новое сообщение из Redis: {new_image_message}")

                if new_image_message:
                    new_image_response = {
                        "id": new_image_message["id"],
                        "unique_name_image": new_image_message["unique_name_image"],
                        "category_type": CrimeType.get(new_image_message["category_type"]),
                        "date": new_image_message["date"],
                        "image": new_image_message["image"],
                    }
                    await websocket.send_json({"new_image": new_image_response})
            await asyncio.sleep(0.1)

    except Exception as e:
        logging.info(f"Ошибка соединения с клиентом {websocket.client.host}: {e}")
    finally:
        logging.info(f"Клиент {websocket.client.host} отключён.")
        connected_clients.remove(websocket)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logging.info("Client connected")
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            logging.info(f"Message received: {data.keys()}")  # Логируем ключи полученных данных

            if "data" in data:
                frame_data = data["data"]
                logging.info("Frame data received")

                # Декодируем base64 в массив NumPy
                img_array = np.frombuffer(base64.b64decode(frame_data), np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)  # Преобразуем в цветное изображение
                logging.info("Frame decoded successfully")

                # Преобразование в черно-белый формат и изменение размера
                resized_frame = cv2.resize(frame, (128, 128))  # Изменение размера до 128x128

                # Кодирование кадра в base64 для отправки обратно, если нужно
                _, buffer = cv2.imencode(".jpg", resized_frame)
                gray_resized_data = base64.b64encode(buffer).decode("utf-8")

                # Сохраняем преобразованный кадр в Redis
                redis_client.rpush("frame_queue", json.dumps({"data": gray_resized_data}))
                logging.info("Processed frame pushed to Redis")
                
    except websockets.ConnectionClosed:
        logging.info("Client disconnected")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting WebSocket server on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
