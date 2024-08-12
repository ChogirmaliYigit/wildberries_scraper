from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DefaultGroupAdmin
from django.contrib.auth.models import Group
from django_apscheduler.admin import DjangoJob
from django_apscheduler.admin import DjangoJobAdmin as BaseDjangoJobAdmin
from django_apscheduler.admin import DjangoJobExecution
from django_apscheduler.admin import (
    DjangoJobExecutionAdmin as BaseDjangoJobExecutionAdmin,
)
from unfold.admin import ModelAdmin

admin.site.unregister(Group)
admin.site.unregister(DjangoJob)
admin.site.unregister(DjangoJobExecution)


@admin.register(Group)
class GroupAdmin(DefaultGroupAdmin, ModelAdmin):
    pass


@admin.register(DjangoJob)
class DjangoJobAdmin(BaseDjangoJobAdmin, ModelAdmin):
    pass


@admin.register(DjangoJobExecution)
class DjangoJobExecutionAdmin(BaseDjangoJobExecutionAdmin, ModelAdmin):
    pass
