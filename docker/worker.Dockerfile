FROM --platform=linux/arm64 python:3.12-slim

ENV TZ Europe/Moscow
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU.UTF-8
ENV LC_ALL ru_RU.UTF-8
ARG BIN_PATH=/worker/

RUN apt-get update -y && \
    apt-get install curl libgl1 libglib2.0-0  -y && \
    apt-get clean

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && cp $HOME/.cargo/bin/* /usr/local/bin

WORKDIR /app
COPY models/* models/
COPY ${BIN_PATH}/requirements.txt .
RUN uv pip install -r requirements.txt --system
COPY ${BIN_PATH}/* .

CMD [ "python3", "worker.py" ]