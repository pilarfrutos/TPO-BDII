FROM mongo:8.0.16
COPY prepare-keyfile.sh init-replica.js healthcheck.js /opt/farmared/
ENTRYPOINT ["bash", "/opt/farmared/prepare-keyfile.sh"]
CMD ["mongod", "--replSet", "rs0", "--keyFile", "/data/keyfile/internal.key", "--bind_ip_all"]
