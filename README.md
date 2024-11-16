# Plex Webhook Docker Setup

This repository contains a Docker setup for the Plex Webhook Handler, which listens for Plex events and triggers corresponding webhooks. The application is designed to be flexible and configurable, including support for sunlight-based scheduling and optional authentication.

## Getting Started

### Prerequisites
- Docker and Docker Compose installed on your system.
- Access to a Docker registry, such as `registry.rlt.sk` (optional).

### Build the Docker Image

You can build the Docker image for multiple platforms using the provided `build.sh` script. Make sure you have Docker Buildx set up for multi-platform support.

1. First, give execute permission to the build script:
   ```sh
   chmod +x build.sh
   ```

2. To build and push the Docker image to a specific registry, run:
   ```sh
   REGISTRY=registry.rlt.sk ./build.sh
   ```
   - If no registry is specified, the image will be built locally without pushing to a registry.
   - If the last commit has a tag, the image will also be tagged with this value.

### Running with Docker Compose

You can use Docker Compose to easily set up and run the Plex Webhook Handler.

### Running with Docker Command

If you prefer not to use Docker Compose, you can run the container directly using `docker run` or pull the prebuilt image:

#### Pull Prebuilt Image
You can use the following command to pull the prebuilt image from GitHub Container Registry:

```sh
docker pull ghcr.io/hanibalsk/plex-playback-webhook:sha256-424ade4ffb4985e9b1f0f865256af6711a467e4900029e80a17026ba6cafeba7.sig
```

You can also pull the `latest` image:

```sh
docker pull ghcr.io/hanibalsk/plex-playback-webhook:latest
```

#### Run Container

```sh
docker run -d   --name plex-webhook-handler   -p 4995:4995   -v /data:/data   -e FLASK_PORT=4995   -e FLASK_ENV=production   -e FLASK_DEBUG=false   registry.rlt.sk/plex-webhook-docker:latest
```
This command will run the Plex Webhook Handler container in the background with the specified configuration.

1. Create a `docker-compose.yml` file with the following content:
   ```yaml
   version: '3.8'

   services:
     plex-webhook:
       image: registry.rlt.sk/plex-webhook-docker:latest
       container_name: plex-webhook-handler
       ports:
         - "4995:4995"
       volumes:
         - /data:/data
       environment:
         FLASK_PORT: 4995
         FLASK_ENV: production
         FLASK_DEBUG: 'false'
       restart: unless-stopped
   ```

2. Start the container using Docker Compose:
   ```sh
   docker-compose up -d
   ```
   This command will run the Plex Webhook Handler as a background service.

### Configuration

The application is configured via a `config.yml` file. Here is an example configuration:

```yaml
webhooks:
  play_resume: "https://example.com/play_resume_webhook"
  pause_stop: "https://example.com/pause_stop_webhook"
  devices:
    - "Living Room TV"
    - "Bedroom TV"
  method: "POST"  # Set to "GET" or "POST" based on your needs
  auth_url: "http://localhost:8000/login"
  auth_password: "potatoes"

sunlight:
  api_url: "https://api.sunrise-sunset.org/json"
  latitude: "48.1486"
  longitude: "17.1077"
  sunrise_offset_minutes: -30  # offset in minutes before/after sunrise
  sunset_offset_minutes: 30    # offset in minutes before/after sunset

schedule:
  enabled: true
  start: "21:00" # enable the service at this time. Could be a string time "HH:mm" or "sunset" or "sunrise"
  end: "06:00" # disable the service at this time. Could be a string time "HH:mm" or "sunset" or "sunrise"

log_file: "/data/logging.log"
```

- **webhooks**: Define URLs for different Plex events and devices to respond to.
- **sunlight**: Control the service based on sunlight conditions with offsets.
- **schedule**: Specify a schedule to enable or disable the service.
- **log_file**: Specify where logs should be saved.

### Authenticating
If an authentication password is provided in the config, the service will try to authenticate using `auth_url` and obtain a token to use for webhooks.

If no password is provided, authentication will be skipped.

### Logging
Logs are written to both the console and a log file (default: `/data/logging.log`). The log file can be configured through the `config.yml` file.

## License
This project is licensed under the MIT License.

## Contributing
Feel free to submit pull requests or open issues to improve this project.
