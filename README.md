# File Upload API

A FastAPI-based service for handling file uploads to AWS S3 with CRUD operations.

## Setup
1. Copy .env.example to .env and populate with your values.
```
cp .env.example .env
```

2. Run docker compose to build and run the container:
```
docker compose up
# or
sudo docker compose up --build
```

## Edit the environment variables for the production environments

1. Install SOPS:
```
brew install sops
```

2. Decrypt the environment file:
```
sops --config .sops/sops.yaml -d -i .sops/prod.env
```

3. Fill in the missing values in the `values.env` file.

4. Encrypt the environment file:
```
sops --config .sops/sops.yaml -e -i .sops/prod.env
```