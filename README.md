# Ansible-based Kubernetes cluster example

This is an example Kubernetes cluster built and managed with Ansible. The example is explained in more detail in Chapter 13 of [Ansible for DevOps](https://www.ansiblefordevops.com/).

## Quick Start Guide

### 1 - Install dependencies (VirtualBox, Vagrant, Ansible)

  1. Download and install [VirtualBox](https://www.virtualbox.org/wiki/Downloads).
  2. Download and install [Vagrant](http://www.vagrantup.com/downloads.html).
  3. [Mac/Linux only] Install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html).

On Windows, run Vagrant with Command Prompt and Ansible inside WSL Ubuntu as described below.

### Windows + WSL

Run in Command Prompt from this repository and wait for all three VMs to finish booting:

```bat
vagrant up
```

Then run in WSL Ubuntu from the same repository:

```bash
cd /mnt/d/Documents/proj01_ansible_deploying_a_microservice_application_on_k8s_with_ansible_and_helm
ansible-playbook -i inventory main.yml
```

The inventory expects the Vagrant insecure SSH key at `~/.vagrant.d/insecure_private_key` inside WSL, with permissions `0600`. If it is missing, copy it from the Windows Vagrant home into that location. Use the Ubuntu distribution explicitly when the default WSL distribution is Docker Desktop (`wsl -d Ubuntu-26.04`).

The playbook waits for SSH after VM creation, disables swap, enables IPv4 forwarding, and configures containerd CRI with systemd cgroups before Kubernetes initialization. It installs the vendored Flannel v0.25.7 manifest using the Vagrant private interface `enp0s8`. The Kubernetes role receives each VM's private IP through `kubernetes_kubelet_extra_args`. No edits to downloaded Galaxy roles are required, so reinstalling dependencies does not erase the project's host configuration. The playbook waits for Flannel on every node, all three nodes to be Ready, and CoreDNS to be available before reporting success.

The containerd configuration disables the unused NRI integration to avoid waiting on its initialization in this lab.

To validate a completely fresh installation, run `vagrant destroy -f` in Command Prompt, then repeat `vagrant up` and the WSL playbook command. This deletes all data inside these three VMs.

### 2 - Build the Virtual Machine

  1. Download this project and put it wherever you want.
  2. Open Terminal, cd to this directory (containing the `Vagrantfile` and this README file).
  3. Run `ansible-galaxy install -r requirements.yml -p ./roles` to install required Ansible roles.
  4. Type in `vagrant up`, and let Vagrant do its magic.

Note: *If there are any errors during the course of running `vagrant up`, and it drops you back to your command prompt, just run `vagrant provision` to continue building the VM from where you left off. If there are still errors after doing this a few times, post an issue to this project's issue queue on GitHub with the error.*

### 3 - Configure your host machine to access the VM.

  1. [Edit your hosts file](http://docs.rackspace.com/support/how-to/modify-your-hosts-file/), adding the line `192.168.56.3  cluster.k8s.test` so you can connect to the VM.

### 4 - Deploy Online Boutique

Install the project roles and collections, then deploy the eleven services from the repository root:

```bash
ansible-galaxy install -r requirements.yml -p ./roles
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory playbooks/online-boutique.yml
```

`playbooks/online-boutique.yml` installs the pinned Helm CLI and Helm Diff plugin from `vars/helm.yml`, clones the upstream `iankisali/microservice-deployment` repository to `/opt/microservice-deployment`, and installs the ten microservice releases plus `redis-cart`. The clone stays unchanged: its values files are inputs, while local overrides in `vars/microservices.yml` configure probes and `vars/resource-profiles.yml` supplies optional per-service resource requests and limits. The frontend Service is NodePort; Part 4 publishes it through an Ingress controller.

To remove only the application and keep the Kubernetes cluster running:

```bash
ansible-playbook -i inventory playbooks/teardown-online-boutique.yml
```

The older `examples/k8s-module.yml` playbook remains available as a separate Nginx example.

### Task 4 - Add hostname-based Ingress

After deploying the application, install Traefik and create the Ingress:

```bash
ansible-playbook -i inventory playbooks/ingress.yml
```

Add `192.168.56.3 boutique.test` to the client machine's hosts file, then browse to `http://boutique.test:30080/`. The Ingress sends that hostname to the `frontend:80` Service. The frontend Service is configured as NodePort to meet the project requirement and can also be reached through the Ingress route.

### Verify and use the application

After the Ingress playbook, verify node readiness, all eleven available Deployments, the checkout Service name, the frontend ClusterIP, the Ingress host/backend, and an HTTP response through hostname routing:

```bash
ansible-playbook -i inventory playbooks/verify.yml
```

The playbook prints the hostname URL after all checks pass. Add an item to the cart, reload, then complete an order to exercise checkout and its downstream services.

### Task 5 - Measure resources and enable probes

The vendored chart adds liveness and readiness probes to the ten application charts. Collect repeated live metrics while browsing the store and completing an order:

```bash
ansible-playbook -i inventory playbooks/measure-resources.yml
```

The play takes about ten minutes. During sampling, exercise the application so the measurements include real requests. It saves raw `kubectl top` output to `reports/part5-resource-samples.txt` and derives per-service requests/limits into `vars/resource-profiles.yml`. The analysis rounds requests up to observed peaks with a 64Mi minimum, uses 2x CPU and 1.5x memory peaks as limit headroom, and applies minimum limits of 250m CPU and 256Mi memory. Short or idle samples can understate startup needs: tiny CPU limits made gRPC probes time out, and tiny memory limits caused OOM kills. These floors are policy choices, not measured facts. Review the generated profiles before applying them. The deploy playbook reads this file; set `microservice_resource_profiles: {}` to leave resource constraints unapplied. Rerun `playbooks/online-boutique.yml` after changing profiles to apply the values. Review the pod configuration with:

```bash
vagrant ssh master
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n microservice get pods
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n microservice describe pod <frontend-pod>
```

The generated profile uses the sampled peak as the request (minimum 10m CPU and 64Mi memory), at least 250m CPU or twice the observed CPU peak when higher, and at least 256Mi memory or 1.5 times the observed memory peak when higher. The raw samples and generated values are evidence for the report; rerun the measurement after changing the workload or traffic scenario.

To demonstrate a liveness-triggered restart and then restore the valid Helm configuration:

```bash
ansible-playbook -i inventory playbooks/demonstrate-probe-restart.yml
```

This briefly installs an unreachable frontend liveness endpoint, waits for Kubernetes to record a container restart, and restores the Helm release even if the observation step fails. Expect a short frontend interruption during the demonstration.

### Task 6 - Scale and drain a worker

Scale the frontend release to two replicas, apply a PodDisruptionBudget that keeps one replica available, then drain and uncordon `node1` through Ansible:

```bash
ansible-playbook -i inventory playbooks/scale-and-drain.yml
```

The PDB constrains voluntary eviction during drain; it cannot protect against an unexpected node failure. The drain uses `--delete-emptydir-data`, so transient data stored in `emptyDir` (including the demo Redis cart) can be lost. The playbook uncordons the worker even if the drain command fails.

## Notes

  - To shut down the virtual machine, enter `vagrant halt` in the Terminal in the same folder that has the `Vagrantfile`. To destroy it completely (if you want to save a little disk space, or want to rebuild it from scratch with `vagrant up` again), type in `vagrant destroy`.

## About the Author

This project was created by [Jeff Geerling](https://www.jeffgeerling.com/) as an example for [Ansible for DevOps](https://www.ansiblefordevops.com/).
