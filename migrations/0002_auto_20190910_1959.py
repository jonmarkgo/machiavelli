# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-09-10 19:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('machiavelli', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitation',
            name='message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='journal',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='order',
            name='code',
            field=models.CharField(choices=[('H', 'Hold'), ('B', 'Besiege'), ('-', 'Advance'), ('=', 'Conversion'), ('C', 'Convoy'), ('S', 'Support')], max_length=1),
        ),
        migrations.AlterField(
            model_name='order',
            name='subcode',
            field=models.CharField(blank=True, choices=[('H', 'Hold'), ('-', 'Advance'), ('=', 'Conversion')], max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='subtype',
            field=models.CharField(blank=True, choices=[('A', 'Army'), ('F', 'Fleet'), ('G', 'Garrison')], max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='type',
            field=models.CharField(blank=True, choices=[('A', 'Army'), ('F', 'Fleet'), ('G', 'Garrison')], max_length=1, null=True),
        ),
        migrations.AlterField(
            model_name='player',
            name='secret_key',
            field=models.CharField(default='', editable=False, max_length=20, verbose_name='secret key'),
        ),
        migrations.AlterField(
            model_name='player',
            name='static_name',
            field=models.CharField(default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='unit',
            name='must_retreat',
            field=models.CharField(blank=True, default='', max_length=5),
        ),
        migrations.AlterField(
            model_name='unit',
            name='type',
            field=models.CharField(choices=[('A', 'Army'), ('F', 'Fleet'), ('G', 'Garrison')], max_length=1),
        ),
    ]
