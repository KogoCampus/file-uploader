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

## S3 Public URL Structure

The public URL for accessing objects in your S3 bucket follows this pattern:
```
https://<bucket-name>.s3.<region>.amazonaws.com/<object-key>
```

Where:
- `<bucket-name>`: Your S3 bucket name
- `<region>`: The AWS region where your bucket is located (e.g., us-east-1, eu-west-1)
- `<object-key>`: The full path and name of your object, including any folder structure

### Example
If:
- Your bucket name is `my-awesome-bucket`
- The object key is `images/photo.jpg`
- Your bucket is in the `us-west-2` region

The public URL would be:
```
https://my-awesome-bucket.s3.us-west-2.amazonaws.com/images/photo.jpg
```
