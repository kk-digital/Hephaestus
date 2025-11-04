"""Database base and declarative_base for Hephaestus."""

import logging
from sqlalchemy.orm import declarative_base

Base = declarative_base()
logger = logging.getLogger(__name__)
