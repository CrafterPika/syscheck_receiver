FROM python:3.13
WORKDIR /syscheck_receiver
COPY . /syscheck_receiver
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /data
EXPOSE 6969/tcp
ENTRYPOINT ["python", "app.py"]
