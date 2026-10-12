# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "geerlingguy/debian11"
  config.ssh.insert_key = false
  config.vm.provider "virtualbox"

  config.vm.provider :virtualbox do |v|
    v.memory = 4096
    v.cpus = 4
    v.linked_clone = true
  end

  # Define three VMs with static private IP addresses.
  boxes = [
    { :name => "master", :ip => "192.168.56.2" },
    { :name => "node1", :ip => "192.168.56.3" },
    { :name => "node2", :ip => "192.168.56.4" },
  ]

  # Provision each of the VMs.
  boxes.each do |opts|
    config.vm.define opts[:name] do |config|
      config.vm.hostname = opts[:name] + ".k8s.test"
      config.vm.network "private_network", ip: opts[:ip]
    end
  end

end
