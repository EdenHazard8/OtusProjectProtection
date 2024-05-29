import pytest

from base_vipnet import FuncVipNet, KeyGeneration
from common import *
from allure_testrail.plugin import allure_testrail


class TestVipNet:
    @pytest.fixture(scope="class")
    def base_scenario(self, vip_net_attributes, token):
        return FuncVipNet(
            vip_net_attributes['path_to_csp_invoke'],
            vip_net_attributes['container_name'],
            vip_net_attributes['user_pin'],
            vip_net_attributes['provtype'],
            vip_net_attributes['hash_alg'],
            vip_net_attributes['key_type'],
            vip_net_attributes['certificate_name'],
            vip_net_attributes['file_path']
        )

    @pytest.fixture(scope="class")
    def command(self):
        return Command()

    @allure_testrail('C1033081')
    def test_key_generation(self, command, base_scenario):
        command.add_command(KeyGeneration(base_scenario))
        command.run_command()
