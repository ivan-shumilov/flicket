#! usr/bin/python3
# -*- coding: utf-8 -*-
#
# Flicket - copyright Paul Bourne: evereux@gmail.com

import base64
from datetime import datetime, timedelta
import os

import bcrypt
from flask import url_for

from application import db, app
from application.flicket.models import Base

user_field_size = {
    'username_min': 4,
    'username_max': 24,
    'name_min': 4,
    'name_max': 60,
    'email_min': 6,
    'email_max': 60,
    'password_min': 6,
    'password_max': 60,
    'group_min': 3,
    'group_max': 64,
    'job_title': 64,
    'avatar': 64
}

flicket_groups = db.Table('flicket_groups',
                          db.Column('user_id', db.Integer, db.ForeignKey('flicket_users.id')),
                          db.Column('group_id', db.Integer, db.ForeignKey('flicket_group.id'))
                          )

class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = query.paginate(page, per_page, False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total,
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page, **kwargs),
                'next': url_for(endpoint, page=page+1, per_page=per_page, **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page-1, per_page=per_page, **kwargs) if resources.has_prev else None
            }
        }

        return data


class FlicketUser(PaginatedAPIMixin, Base):
    """
    User model class
    """
    __tablename__ = 'flicket_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(user_field_size['username_max']), index=True, unique=True)
    name = db.Column(db.String(user_field_size['name_max']))
    password = db.Column(db.LargeBinary(user_field_size['password_max']))
    email = db.Column(db.String(user_field_size['email_max']), unique=True)
    date_added = db.Column(db.DateTime)
    date_modified = db.Column(db.DateTime, onupdate=datetime.now)
    job_title = db.Column(db.String(user_field_size['job_title']))
    avatar = db.Column(db.String(user_field_size['avatar']))
    total_posts = db.Column(db.Integer, default=0)
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)

    def __init__(self, username, name, email, password, date_added, job_title=None):
        self.username = username
        self.name = name
        self.password = password
        self.email = email
        self.job_title = job_title
        self.date_added = date_added

    def __repr__(self):
        return '<User {}>'.format(self.username)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_admin(self):
        """ returns true if the user is a member of the 'flicket_admin' group"""
        user = FlicketUser.query.filter_by(id=self.id).first()
        for g in user.flicket_groups:
            if g.group_name == app.config['ADMIN_GROUP_NAME']:
                return True

    def get_id(self):
        return str(self.id)

    def check_password(self, password):
        result = FlicketUser.query.filter_by(username=self.username)
        if result.count() == 0:
            return False
        result = result.first()
        if bcrypt.hashpw(password.encode('utf-8'), result.password) != result.password:
            return False
        return True

    def to_dict(self):
        '''
        Returns a dictionary object about the user.
        :return:
        '''

        data = {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'job_title': self.job_title if self.job_title else 'unknown',
            'total_posts': self.total_posts,
            'links': {
                'self': url_for('bp_api_v2.get_user', id=self.id)
            }
        }

        return data

    def get_token(self, expires_in=36000):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds=60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = FlicketUser.query.filter_by(token=token).first()
        if user is None or user.token_expiration < datetime.utcnow():
            return None
        return user


class FlicketGroup(Base):
    """
    Flicket Group model class
    """
    __tablename__ = 'flicket_group'
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(user_field_size['group_max']))
    users = db.relationship(FlicketUser,
                            secondary=flicket_groups,
                            backref=db.backref('flicket_groups',
                                               lazy='dynamic',
                                               order_by=group_name
                                               )
                            )

    # this is for when a group has many groups
    # ie everyone in group 'flicket_admin' can be a member of group 'all'
    # parents = db.relationship('Group',
    #                           secondary=group_to_group,
    #                           primaryjoin=id==group_to_group.c.parent_id,
    #                           secondaryjoin=id==group_to_group.c.child_id,
    #                           backref="children",
    #                           remote_side=[group_to_group.c.parent_id])

    def __init__(self, group_name):
        self.group_name = group_name

    @property
    def __repr__(self):
        return self.group_name
