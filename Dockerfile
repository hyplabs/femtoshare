FROM python:3

ENV PORT=8000
ENV TITLE=femtoshare
ENV UID=1000

RUN mkdir -p /usr/src/femtoshare/
RUN mkdir -p /usr/src/femtoshare/files
RUN useradd -u $UID femto

COPY femtoshare.py /usr/src/femtoshare

EXPOSE $PORT


RUN mkdir -p /files
RUN chown -R femto:femto /files
VOLUME /files
WORKDIR /usr/src/femtoshare
USER femto

CMD python femtoshare.py --public --port $PORT --files-dir /files --title $TITLE