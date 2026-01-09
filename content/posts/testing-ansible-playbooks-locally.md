+++
date = '2026-01-03T17:25:56+01:00'
draft = false
title = 'Testing Ansible Playbooks Locally'
description = 'Set up a local testing environment for Ansible playbooks using Vagrant and VirtualBox. Learn how to safely test infrastructure changes before deploying to production with a step-by-step guide.'
tags = ['Ansible', 'DevOps', 'Infrastructure', 'Testing', 'Vagrant']
categories = ['DevOps', 'Infrastructure']
+++

At [Python Discord](https://pythondiscord.com), we use [Ansible](https://docs.ansible.com/) to set up a part of our
infrastructure.

A "bad" pattern we had is that we always tested these playbooks in production. I say "bad" because I think this can be a
pretty controversial topic, and I've worked in a lot of companies who do this, or cheated their way around it, but that's
off-topic for now.

This led us to setting up a way to easily test our playbooks, but on a similar environment, without running the risk of
unintentionally performing an undesired/destructive action or whatever.


## Disclaimer

This post assumes familiarity with:
- [Ansible fundamentals](https://docs.ansible.com/ansible/latest/getting_started/index.html) (playbooks, roles, inventory)
- [Vagrant basics](https://developer.hashicorp.com/vagrant/tutorials/getting-started) (managing VMs via Vagrantfiles)

I'll explain concepts briefly as they come up, but having baseline knowledge will help you follow along more easily.

## Prerequisites

At the time of writing this, I was on macOS Tahoe 26.1, using `HomeBrew` version `5.0.8-43-gfe0a384`.

To do this, you'll have to install:
* `virtualbox` version `7.2.4,170995`
* `vagrant` version `2.4.9`

## Project overview

The project we'll be working on in this tutorial is a made up version for the sake of simplicity.

The one we use at Python Discord is open source, and can be found in our [GitHub repository](https://github.com/python-discord/infra/tree/040ae8a484c2b27b164f751b0dd57f921e8aae67/ansible).

The project root's will be at the `infra` directory

```text
└── infra/
    ├── Vagrantfile
    ├── playbook.yml
    ├── roles/
    │   └── hello_world/
    │       └── tasks/
    │           └── main.yml
    └── inventory/
        ├── hosts.yaml
        └── vagrant_hosts.yaml

```

* `Vagrantfile`: The `Vagrant` configuration that we'll use to configure our VMs to simulate our servers.
* `playbook.yml`: The `Ansible` playbook that orchestrates all the roles/tasks that need to run on our infra
* `roles/hello_world/tasks/main.yml`: The main task of the `hello_world` [Ansible Role](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html)
* `inventory/hosts.yaml`: The production hosts file
* `inventory/vagrant_hosts.yaml`: The hosts to use when testing the playbooks locally with `Vagrant`

You can find the content of all of these files in the [File content section](#file-contents)

## Setting Up Vagrant 
Very quickly, `Vagrant` is a tool that allows you to configure/provision/manage virtual machines on your host in complete isolation.

This configuration and provisioning is done via a [VagrantFile](https://developer.hashicorp.com/vagrant/docs/vagrantfile)
which allows you to write some sort of manifest in Ruby that'll set up the virtual machines for you.

### General box configuration

Vagrant allows you to have either "global" or per VM configuration.
We actually need and will be using both, but the one in this section explains the global one. 

```ruby
Vagrant.configure("2") do |config|
    # This is the base image that will be used for all VMs
    config.vm.box = "bento/debian-13"
    
    # This is provisioning that will run on all VMs, but custom provisioning per specific VM is also possible.    
    config.vm.provision "shell", inline: <<-SHELL
        sudo apt-get update
        apt-get install -y python3 python3-pip sshpass
    SHELL
end
```

### Configuring the control node/VM
The playbook/roles, etc. need to run from what Ansible calls the [control node](https://docs.ansible.com/ansible/latest/getting_started/basic_concepts.html#control-node).


The following is the `Vagrant` configuration to create that node.

```ruby
Vagrant.configure("2") do |config|
    # ...
    # Global provisioning seen previously has been omitted to focus solely on the control node's config
    
    # Define `control` as the primary VM
     
    config.vm.define "control", primary: true do |control|
    
        # Copy the content of the folder running `Vagrant` into control's `/infra` folder
        # This allows us to have the playbooks/roles that will run from the control node
        config.vm.synced_folder ".", "/infra", type: "rsync"
    
        # We assign a static IP for all VMs to easily identify them
        control.vm.network "private_network", ip: "192.168.56.2", virtualbox__intnet: true
        control.vm.hostname = "control"
    
        # Install Ansible on the control node, required to run the playbooks 
        control.vm.provision "Install Ansible", type: "shell", inline: <<-SHELL
            apt-get update
            apt-get install -y ansible
        SHELL
    
        # SSH configuration to allow the control node to connect to all managed nodes effortlessly
        control.vm.provision "setup_ssh", type: "shell", privileged: false, run: "never", inline: <<-SHELL
                ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa <<< y
                ssh-keyscan 192.168.56.3 >> ~/.ssh/known_hosts
                sshpass -p vagrant ssh-copy-id 192.168.56.3
        SHELL
        
        # Specify the provider to use for creating the VM 
        control.vm.provider "virtualbox" do |v|
            v.name = "control_node"
        end
    end
end
```


#### SSH Provisioning

You might have noticed that `setup_ssh` that is configured to never execute upon running `vagrant` up.

The reason we have it in the first place is to allow the `control` node to easily connect over SSH to `hopper`.

We do this by:
* Including `hopper` in the list of `control`'s known hosts
* Copying `control`'s public key over to `hopper`

However, it's set to `never` because we want to run the provisioning when both `control` and `hopper` are up and running,
since it requires fetching `hopper`'s host key, and adding `control`'ls public key to `hopper`



### Managed node's configuration
The actual machines being configured by Ansible are called the [managed nodes](https://docs.ansible.com/ansible/latest/getting_started/basic_concepts.html#managed-nodes).

In our case, we will be configuring one VM only to keep things simple.

If you want to manage and configure multiple VMs, the principle is the same, you just need to replicate the configuration
for this one, and alter the assigned static ip.

```ruby
Vagrant.configure("2") do |config|
    # ...
    # Global provisioning seen previously has been omitted to focus solely on the control node's config
    
    config.vm.define "hopper" do |hopper|
        
        # We assign a static IP for the managed node to easily identify it
        hopper.vm.network "private_network", ip: "192.168.56.3", virtualbox__intnet: true
        hopper.vm.hostname = "hopper"
        # Disable any folder syncing, as the machines are supposedly fresh/empty
        hopper.vm.synced_folder '.', '/vagrant', disabled: true
        
        # Chose the provider to create the VM. 
        hopper.vm.provider "virtualbox" do |v|
            v.name = "hopper"
        end
    end
end
```

This one's quite simple, we're basically just creating a fresh VM, and assigning a static ip of `192.168.56.3` to it
so that we can easily configure and target it in `Ansible`'s host inventory.


### Complete VagrantFile content

This is included here just to see what the `Vagrantfile` will finally look like once we've combined all the previously
explained sections.


{{< code ruby >}}

Vagrant.configure("2") do |config|
    config.vm.box = "bento/debian-13"
    config.vm.provision "shell", inline: <<-SHELL
        sudo apt-get update
        apt-get install -y python3 python3-pip sshpass
    SHELL

    config.vm.define "control", primary: true do |control|
        config.vm.synced_folder ".", "/infra", type: "rsync"
        control.vm.network "private_network", ip: "192.168.56.2", virtualbox__intnet: true
        control.vm.hostname = "control"
        control.vm.provision "Install Ansible", type: "shell", inline: <<-SHELL
	    apt-get update
	    apt-get install -y ansible
        SHELL

	control.vm.provision "setup_ssh", type: "shell", privileged: false, run: "never", inline: <<-SHELL
	    ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa <<< y
	    ssh-keyscan 192.168.56.3 >> ~/.ssh/known_hosts
	    sshpass -p vagrant ssh-copy-id 192.168.56.3
        SHELL

        control.vm.provider "virtualbox" do |v|
            v.name = "control_node"
        end
    end

    config.vm.define "hopper" do |hopper|
        hopper.vm.network "private_network", ip: "192.168.56.3", virtualbox__intnet: true
        hopper.vm.hostname = "hopper"
        hopper.vm.synced_folder '.', '/vagrant', disabled: true
        hopper.vm.provider "virtualbox" do |v|
            v.name = "hopper"
        end
    end
end

{{< /code >}}

### Setting Up The Virtual Machines

Enough with the boring configuration stuff. It's now time to bring those VMs up and running in order to be able to use them.

This is actually quite simple, and requires running the following two commands from within the `infra` directory

```bash
vagrant up
vagrant provision control --provision-with setup_ssh 
```

## Running The Playbooks

Once the VMs are provisioned, we can now move on to testing our `Ansible` playbooks.

First, we ssh into `control`

```bash
vagrant ssh control
```

Then, move into the `infra` folder.

```bash
cd /infra
```

Finally, we run the playbooks
```bash
ansible-playbook playbook.yml --inventory inventory/vagrant_hosts.yml
```

You can verify that the `hello_world` role ran by running the following commands

```bash
vagrant ssh hopper -c "cat ~/hello.txt"
```

This will display "Hello World" in the console, proving the role ran successfully

> It's important to note that whenever you change something, e.g. the roles, the playbook, etc. you're gonna have to
> sync those into the VM by running `vagrant rsync`.

## Cleanup

When you're done testing or want to start fresh, simply destroy all VMs by running:

```bash
vagrant destroy -f
```

## Final thoughts
While I was writing this, it came to my knowledge that there is an `Ansible` provisioner that can be used to do all of this
but differently.

However, I still wanted to demonstrate how we actually did it back then.

I must say that this is obviously not the only way to test playbooks locally, but it is the one we decided to use back then.

I might make updates to this post at some point to illustrate how we could the Ansible provisioner instead, or maybe even
test the playbooks on a docker container instead of using `Vagrant`.



## File contents

This section exists to display the contents of all the different files that take part of this tutorial, in case someone
wants to test this end to end.

### Playbook.yml

{{< code yaml >}}
- name: Setup infra
  hosts: all
  roles:
    - hello_world
{{< /code >}}


### roles/hello_world/tasks/main.yml

{{<code yaml>}}
- name: Create hello world file in user's home directory
  ansible.builtin.copy:
    content: "Hello world"
    dest: "{{ ansible_env.HOME }}/hello.txt"
    mode: 'a=r'
{{< /code >}}

### vagrant_hosts.yml

{{<code yaml>}}
all:
  hosts:
    hopper:
      ansible_host: 192.168.56.3
      ip: 192.168.56.3
      access_ip: 192.168.56.3
{{< /code >}}

