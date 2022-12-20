FROM python:3.9

COPY requirements.txt ./
RUN pip install --upgrade pip 
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/power
COPY . /usr/src/power

CMD [ "python3.9", "power.py" ]
