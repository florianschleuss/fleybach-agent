FROM python:3.9

COPY requirements.txt ./
RUN pip install --upgrade pip 
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/temperature
COPY . /usr/src/temperature

CMD [ "python3.9", "temperature.py" ]
