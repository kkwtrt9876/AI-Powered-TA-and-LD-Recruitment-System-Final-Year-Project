FROM ubuntu:20.04

RUN apt-get update && apt-get install -y g++ \
    && useradd -ms /bin/bash runner

WORKDIR /app
USER runner

