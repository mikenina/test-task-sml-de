FROM postgres:17

COPY init/01_schema.sql    /docker-entrypoint-initdb.d/01_schema.sql
COPY init/02_synthetic.sql /docker-entrypoint-initdb.d/02_synthetic.sql
COPY init/03_dwh_init.sql  /docker-entrypoint-initdb.d/03_dwh_init.sql