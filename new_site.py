from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from ipam.models import IPAddress
from tenancy.models import Tenant, TenantGroup
from extras.scripts import *


class NewBranchScript(Script):
    class Meta:
        name = "Новый офис"
        description = "Добавить новый офис"
        # field_order = ['site_name', 'switch_count', 'switch_model']

    site_name = StringVar(
        description="Название офиса"
    )
    slug = StringVar(
        description="Имя латиницей, из спец. символов \"-\""
    )
    tenant_group = ObjectVar(
        model=TenantGroup,
        required=False
    )
    tenant = ObjectVar(
        model=Tenant,
        description="Организация",
        query_params={
            'group_id': '$tenant_group'
        }
    )
    physical_address = StringVar(
        description="Физический адрес офиса"
    )
    manufacturer_router = ObjectVar(
        model=Manufacturer,
        required=False
    )
    router_model = ObjectVar(
        description="Модель роутера",
        model=DeviceType,
        query_params={
            'manufacturer_id': '$manufacturer_router'
        }
    )
    public_ip = IPAddressWithMaskVar(
        description="Публичный IP-адрес",
        required=False
    )
    public_interface = StringVar(
        default="eth1",
        description="Интерфейс для публичного адреса, прим. eth1. Необходимо указать, если прописан ip.",
        required=False
    )
    private_ip = IPAddressWithMaskVar(
        description="Приватный (внутренний) IP-адрес"
    )
    private_interface = StringVar(
        default="bridge1",
        description="Интерфейс для приватного адреса, прим. bridge1. Необходимо указать, если прописан ip."
    )
    manufacturer_switch = ObjectVar(
        model=Manufacturer,
        required=False
    )
    switch_model = ObjectVar(
        description="Модель свитча",
        model=DeviceType,
        query_params={
            'manufacturer_id': '$manufacturer_switch'
        }
    )
    switch_count = IntegerVar(
        description="Количество свитчей"
    )

    def run(self, data, commit):

        # Create the new site
        site = Site(
            name=data['site_name'],
            slug=data[ 'slug' ],
            tenant=data[ 'tenant' ],
            physical_address=data[ 'physical_address' ],
            status=SiteStatusChoices.STATUS_PLANNED
        )
        site.full_clean()
        site.save()
        self.log_success(f"Created new site: {site}")

        router_role = DeviceRole.objects.get(name='Router')

        addr_private = IPAddress(
            address=data[ 'private_ip' ],
            tenant=data[ 'tenant' ],
        )
        addr_private.save()

        router = Device(
            device_type=data[ 'router_model' ],
            name=f'{site.slug.upper()}-R1',
            site=site,
            status=DeviceStatusChoices.STATUS_PLANNED,
            device_role=router_role,
            primary_ip4=addr_private
        )
        router.save()

        self.log_success(f"Created new router: {router}")


        bridge = router.interfaces.get(name=data[ 'private_interface' ])
        addr_private.assigned_object = bridge

        wan = router.interfaces.get(name=data[ 'public_interface' ])
        addr_public = IPAddress(
            address=data[ 'public_ip' ],
            tenant=data[ 'tenant' ],
        )
        addr_public.save()
        addr_public.assigned_object = wan


        # Create access switches
        switch_role = DeviceRole.objects.get(name='Access Switch')
        for i in range(1, data[ 'switch_count' ] + 1):
            switch = Device(
                device_type=data[ 'switch_model' ],
                name=f'{site.slug}-SW{i}',
                site=site,
                status=DeviceStatusChoices.STATUS_PLANNED,
                device_role=switch_role
            )
            switch.full_clean()
            switch.save()
            self.log_success(f"Created new switch: {switch}")

        # Generate a CSV table of new devices
        output = [
            'name,make,model'
        ]
        for switch in Device.objects.filter(site=site):
            attrs = [
                switch.name,
                switch.device_type.manufacturer.name,
                switch.device_type.model
            ]
            output.append(','.join(attrs))

        return '\n'.join(output)
