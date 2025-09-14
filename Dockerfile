# Force x86_64 userspace (Wine + MT5 need this)
FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    DISPLAY=:1 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES="mscoree,mshtml=" \
    WINEPREFIX=/root/.wine

# Base deps + Linux Python for Telethon
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget gnupg2 software-properties-common \
    xvfb xauth xdotool cabextract unzip locales tzdata \
    python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*

# WineHQ for jammy + i386 multiarch
RUN dpkg --add-architecture i386 \
 && mkdir -pm755 /etc/apt/keyrings \
 && curl -fsSL https://dl.winehq.org/wine-builds/winehq.key \
    | gpg --dearmor -o /etc/apt/keyrings/winehq-archive.key \
 && printf "Types: deb\nURIs: https://dl.winehq.org/wine-builds/ubuntu/\nSuites: jammy\nComponents: main\nSigned-By: /etc/apt/keyrings/winehq-archive.key\n" \
    > /etc/apt/sources.list.d/winehq.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      winehq-stable wine-stable wine-stable-i386:i386 winbind \
 && rm -rf /var/lib/apt/lists/*
 
# Download MT5 installer
WORKDIR /opt/mt5
RUN wget -q https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe

# Bot code
WORKDIR /app
COPY copier.py /app/copier.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]