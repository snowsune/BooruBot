# See here https://hub.docker.com/r/gorialis/discord.py/
#FROM gorialis/discord.py
FROM python:3.10-slim

# Authors
LABEL authors="31870999+KenwoodFox@users.noreply.github.com"

# Set the name of our app
ARG APP_NAME=boorubot
ENV APP_NAME=${APP_NAME}

# App home
ARG HOME="/app"
ENV HOME=${HOME}

# Upgrade pip
RUN pip install --upgrade pip --no-cache-dir

# Set workdir
WORKDIR ${HOME}

# Add any packages we need
RUN apt update && apt install python-dev-is-python3 ffmpeg curl -y

# Copy in all requirements
ADD requirements requirements/

# Install normal reqs
RUN pip install -r requirements/requirements.txt --no-cache-dir
# Install testing reqs
RUN pip install -r requirements/test_requirements.txt --no-cache-dir

# Add /bin to path
RUN mkdir -p ${HOME}/bin
ENV PATH $PATH:${HOME}/bin

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ${HOME}/bin/yt-dlp
RUN chmod a+rx ${HOME}/bin/yt-dlp
RUN yt-dlp -U

# Copy in everything else
ADD . ${HOME}

# Get the current git version
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

# Install our app in edit mode using pip
RUN pip install -e ${HOME} --no-cache-dir

# Drop root and change ownership of /app to app:app
RUN chown -R ${USER_ID}:${GROUP_ID} ${HOME}
USER ${USER_ID}

# The `|| exit 1` isn't required but it's good practice anyway.
HEALTHCHECK CMD discordhealthcheck || exit 1

# Run the entrypoint bin
ENTRYPOINT ["entrypoint"]
