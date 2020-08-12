FROM python:3.8-buster as netpaca
RUN pip install pip -U && pip install -e git+https://github.com/netpaca/netpaca@master#egg=netpaca[all]

FROM netpaca
WORKDIR /workdir
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
RUN pip install .

