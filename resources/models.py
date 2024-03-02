from environs import Env
from peewee import *

env = Env()
env.read_env(path='../.env')

database = env.str('database')
user = env.str('user')
password = env.str('password')
host = env.str('host', default='127.0.0.1')
port = env.int('port', default=5432)

db = PostgresqlDatabase(database=database, user=user, password=password, host=host, port=port)


class TableTrustedShopsDe(Model):
    company_name = TextField()
    organization_name = TextField()
    address = TextField()
    phone = TextField()
    website = TextField()
    email = TextField(unique=True, null=False)
    company_url = TextField()
    rating_count = CharField()
    rating_value = CharField()
    main_category = CharField()
    sub_category = CharField()

    class Meta:
        database = db
        table_name = 'Table_TrustedShopsDe'


class TableMailDB(Model):
    address = TextField()
    category = TextField()
    company_name = TextField()
    email = TextField()
    is_send = BooleanField()
    phone = TextField()
    website = TextField()
    source_site = CharField(max_length=250)

    class Meta:
        database = db
        table_name = 'Table_MailDB'
