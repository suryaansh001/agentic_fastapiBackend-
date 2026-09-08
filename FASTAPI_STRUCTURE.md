backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── env.validation.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── base.py
│   │   └── migrations/
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/
│   │           └── __init__.py
│   ├── dependencies/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── rbac.py
│   │   ├── pagination.py
│   │   ├── caching.py
│   │   └── current_user.py
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── logging.py
│   │   ├── error_handler.py
│   │   ├── request_logging.py
│   │   └── cors.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── pagination.py
│   │   ├── filters.py
│   │   ├── validators.py
│   │   ├── sorting.py
│   │   └── crud.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_companies.py
│   │   ├── test_contacts.py
│   │   ├── test_deals.py
│   │   ├── test_activities.py
│   │   ├── test_auth.py
│   │   └── test_fields.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── contracts.py
│   │   ├── dependencies.py
│   │   └── hooks.py
│   ├── companies/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── contracts.py
│   │   ├── domain.py
│   │   └── directory.py
│   ├── contacts/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── contracts.py
│   │   └── enrichment.py
│   ├── deals/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── contracts.py
│   │   └── staging.py
│   ├── activities/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── contracts.py
│   ├── fields/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── contracts.py
│   ├── conversations/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── contracts.py
│   ├── workspace/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── contracts.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── saved-views/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   └── schemas.py
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── module.py
│   │   └── service.py
│   ├── archive/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── config.py
│   ├── currency/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── api-keys/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── service.py
│   ├── tracking/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   └── models.py
│   ├── slack/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── sso/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── mailbox/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── google/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   └── models.py
│   ├── microsoft/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   └── models.py
│   ├── backfill/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   └── models.py
│   ├── crm/
│   │   ├── __init__.py
│   │   ├── activity_stamp.py
│   │   ├── bulk.py
│   │   ├── values.py
│   │   └── enrichment_log.py
│   └── trpc/
│       ├── __init__.py
│       ├── context.py
│       ├── error_handler.py
│       ├── openapi.py
│       └── middlewares/
│           ├── __init__.py
│           ├── auth.py
│           ├── logging.py
│           └── error_handler.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── __init__.py
│       └── README
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_companies.py
│   ├── test_contacts.py
│   ├── test_deals.py
│   ├── test_activities.py
│   ├── test_auth.py
│   └── test_fields.py
├── scripts/
│   ├── db_migrate.py
│   ├── db_seed.py
│   └── build.py
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── Dockerfile
└── .env.example
