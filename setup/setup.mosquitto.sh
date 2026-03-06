#!/bin/bash

sudo apt install mosquitto mosquitto-clients -y
sudo cp mosquitto.conf /etc/mosquitto/conf.d/
sudo systemctl restart mosquitto.service