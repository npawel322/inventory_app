from django.contrib import admin
from .models import Office, Room, Desk, AssetCategory, Asset, Person, Loan

admin.site.register(Office)
admin.site.register(Room)
admin.site.register(Desk)
admin.site.register(AssetCategory)
admin.site.register(Asset)
admin.site.register(Person)
admin.site.register(Loan)
