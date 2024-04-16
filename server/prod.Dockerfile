FROM python:3.10.13-slim-bullseye
ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    gcc \
    libpq-dev \
    curl \
    wget \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip setuptools

# below two lines are required for ppc64le server
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH /root/.cargo/bin:$PATH

# install miniconda
RUN mkdir -p ~/miniconda3 && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-py310_23.10.0-1-Linux-ppc64le.sh -O ~/miniconda3/miniconda.sh && \
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3 && \
    rm -rf ~/miniconda3/miniconda.sh 

ENV PATH=/root/miniconda3/bin:$PATH 


# env to build the cryptography msgpack package
ENV PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/local/lib/pkgconfig
ENV OPENSSL_DIR=/root/miniconda3/ssl
ENV POWERPC64LE_UNKNOWN_LINUX_GNU_OPENSSL_LIB_DIR=/usr/lib/powerpc64le-linux-gnu
ENV OPENSSL_LIB_DIR=/usr/lib/powerpc64le-linux-gnu
ENV POWERPC64LE_UNKNOWN_LINUX_GNU_OPENSSL_INCLUDE_DIR=/usr/include/openssl
ENV OPENSSL_INCLUDE_DIR=/usr/include/openssl

RUN pip install poetry

# Turn off Poetry's virtualenv to ensure dependencies are installed in the system Python environment
RUN poetry config virtualenvs.create false

# Copy only requirements to cache them in docker layer
WORKDIR /app
COPY README.md pyproject.toml poetry.lock /app/

# Poetry install
ARG INSTALL_DEV=false
RUN poetry update
RUN if [ "$INSTALL_DEV" = "true" ]; then poetry install; else poetry install --only main; fi

# install library
COPY ./lib /app/lib
WORKDIR /app/lib
RUN conda install conda-forge::grpcio
RUN pip install .
RUN rm -rf /app/lib

# Make server
WORKDIR /app
COPY . /app
EXPOSE 8000
ENV DJANGO_DEBUG=false

RUN rustup self uninstall -y
RUN rm -rf ~/.cargo
RUN rm -rf ~/.rustup

ENTRYPOINT [ "/app/entrypoint.sh" ]
