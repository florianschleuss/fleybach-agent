FROM python:3.9

COPY requirements.txt ./
RUN pip install --upgrade pip 
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/device
COPY . /usr/src/device

CMD [ "python3.9", "device.py" ]
