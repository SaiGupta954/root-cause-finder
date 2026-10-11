FROM python:3.12-alpine
RUN pip install --no-cache-dir supervisor
COPY supervisord.conf /etc/supervisord.conf
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
