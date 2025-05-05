#!/bin/bash
# Set Gunicorn timeout for large uploads
mkdir -p /opt/python/etc
echo 'timeout="600"' > /opt/python/etc/gunicorn.conf
chmod 644 /opt/python/etc/gunicorn.conf