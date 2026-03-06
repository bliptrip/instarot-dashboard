#!/bin/bash

sudo apt install nginx -y
sudo cp instarot.nginx.conf /etc/nginx/sites-available/instarot
sudo ln -s /etc/nginx/sites-available/instarot /etc/nginx/sites-enabled
sudo nginx -t && sudo systemctl reload nginx