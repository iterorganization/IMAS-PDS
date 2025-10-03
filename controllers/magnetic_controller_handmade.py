# Based on work by Rémy Nouailletas & Guillaume Gros

import logging
import os
import math
import matplotlib.pyplot as plt
import copy

import numpy as np

import imas
from imas import imasdef


from libmuscle import Grid, Instance, Message
from ymmsl import Operator

def MagneticController() -> None:
    """A magnetic controller for ITER (experimental) in python with IDS"""

    logger = logging.getLogger()
    logger.info('time manager started')
    
    instance = Instance({
            Operator.F_INIT: ['equilibrium_f_init'],
            Operator.S: ['equilibrium_s, pf_active_s'],
            Operator.O_I: ['pf_active_o_i']})
    
    while (instance.reuse_instance()):
      equilibrium_ref, t_cur, t_next = receive_ids(instance, 'equilibrium', 'f_init')
      with imas.DBEntry("imas:memory?path=/", "w") as db:
        db.put(equilibrium_data)
        t_next = 1
        while t_next is not None:
          equilibrium, t_cur, t_next = receive_ids(instance, 'equilibrium', 's')
          pf_active, t_cur, t_next = receive_ids(instance, 'pf_active', 's')
          eq_ref_slice = db.get_slice(
              ids_name="equilibrium",
              time_requested=t_cur,
              interpolation_method=CLOSEST_INTERP,
          )
          pf_active_out = apply_controller(eq_ref_slice, equilibrium, pf_active)
          send_ids(instance, pf_active_out, 'pf_active', 'o_i')
        


      while (t_cur < t_max):
         if t_cur>t_start:
         # read data from the system for the next step
                     
            #########################################
            #### IMPLEMENTATION OF THE CONTROLLER ###
            #########################################    
            
            err_Icoil_cur=Icoil_cur-Icoil_ref_cur + np.matmul(B_map,dIcoil_ref_cur)

            for j in range(14):
              Vsupply0[j]=0.0
            Vsupply0[2]=dIcoil_ref_cur[2] #plasma current control
            Vsupply0[3]=dIcoil_ref_cur[2] #plasma current control

            #### COMPUTE REQUEST FOR THE NEXT TIME ###
               
            err_rgeom_next=rgeom_next-rgeom_ref_cur
            err_zgeom_next=zgeom_next-zgeom_ref_cur
            err_ip_next=ip_next-ip_ref_cur

            Xi_rgeom_next=Xi_rgeom_cur+dt_cur*err_rgeom_next
            Xi_zgeom_next=Xi_zgeom_cur+dt_cur*err_zgeom_next
            Xi_ip_next=Xi_ip_cur+dt_cur*err_ip_next
               
            dIcoil_ref_next[0]=Kp_rgeom*err_rgeom_next+Ki_rgeom*Xi_rgeom_next
            dIcoil_ref_next[1]=Kp_zgeom*err_zgeom_next+Ki_zgeom*Xi_zgeom_next
            dIcoil_ref_next[2]=Kp_ip*err_ip_next+Ki_ip*Xi_ip_next
                           
            #Error Coils currents with plasma position
            err_Icoil_next=Icoil_next-Icoil_ref_cur + np.matmul(B_map,dIcoil_ref_next)
            
            #Integration
            Xi_Icoil_next=Xi_Icoil_cur+dt_cur*(np.matmul(B_Icoil_ctr,err_Icoil_next))                                                                             

         else:
            err_rgeom_cur=0
            err_zgeom_cur=0
            err_ip_cur=0
            dIcoil_ref_cur[0]=0
            dIcoil_ref_cur[1]=0
            dIcoil_ref_cur[2]=0
            err_Icoil_cur=np.zeros((13,1))
                     
         Vcoil_cur=np.matmul(D_Icoil_ctr,err_Icoil_cur) + np.matmul(C_Icoil_ctr,Xi_Icoil_cur)+Vsupply0

         voltage_request=copy.deepcopy(Vcoil_cur)
         voltage_request=np.minimum(voltage_request,Vmax)
         voltage_request=np.maximum(voltage_request,Vmin)
         logger.info('--------------------------')
         logger.info('voltage_request:') 
         PF_resistance = np.array(0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0005,0.0057,0.00791)
         for ii in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
            logger.info('%f V',voltage_request[ii])      
            #Put supply voltage into the pf_active IDS
            print(voltage_request[ii])
            pf_active_out.supply[ii].resistance=PF_resistance[ii]
            pf_active_out.supply[ii].voltage.data=np.array(voltage_request[ii])
            pf_active_out.supply[ii].voltage.time=np.array([t_cur])
         logger.info('--------------------------')  

         pf_active_out.time=np.array([t_cur])
         #############################
         #### SEND VOLTAGE REQUEST ###
         #############################
         out_msg = Message(t_cur, t_next, pf_active_out)
         instance.send('pf_active_out', out_msg)
         t_next=t_cur+dt


def get_values():
    values = {}
    ## Controller parameters
    A_Icoil_ctr=np.zeros((13,13)) #useless in our case

    B_Icoil_ctr=np.array([[1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0],
                          [0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0]])
    
    C_Icoil_ctr=np.array([[0.0005, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0005, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0005, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0005, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0005, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, -0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0004, -0.0001, 0.0001, 0.0001, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, -0.0001, 0.0004, 0.0001, 0.0001, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0001, 0.0001, 0.0004, -0.0001, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0001, 0.0001, -0.0001, 0.0004, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, -0.0001, -0.0001, 0.0001, 0.0001, 0.0000, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0005, 0.0000, 0.0000],
                          [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, -0.000068, 0.0000]])

    K_D=-2.0e3 #Proportional coef for PF coils currents
    K_C=-1.0e2 #Integral coef for PF coils currents

    D_Icoil_ctr=C_Icoil_ctr

    D_Icoil_ctr=D_Icoil_ctr*K_D
    C_Icoil_ctr=C_Icoil_ctr*K_C

    # PS saturation voltage
    Vmax=np.array([[45000.0],[45000.0],[45000.0],[45000.0],[45000.0],[45000.0],[48000.0],[55000.0],[55000.0],[55000.0],[55000.0],[22500.0],[48000.0],[60000.0]])
    Vmin=np.array([[-45000.0],[-45000.0],[-45000.0],[-45000.0],[-45000.0],[-45000.0],[-48000.0],[-55000.0],[-55000.0],[-55000.0],[-55000.0],[-22500.0],[-48000.0],[-60000.0]])
    
    ## integral state for coil current control
    Xi_Icoil_cur=np.zeros((13,1))
    
    # Refence
    Vsupply0=np.zeros((14,1))
    Vcoil_cur=np.zeros((14,1))

    #Icoils scenario (-Icoils from inverse NICE due to cocos(?))
    Icoil_ref_scenario = -np.array([[2875.67036687,2875.67036687,7038.06,6117.13], 
                                    [-13890.51718003,-13890.51718003,-11297.4,-13798.6], 
                                    [-13137.60845427,-13137.60845427, -35963.1,-34326.3], 
                                    [-14759.83893168,-14759.83893168,-12062.5,-13966.6], 
                                    [7462.2572929, 7462.2572929 ,11727.4,10554.2,], 
                                    [5122.65904897, 5122.65904897,28934,22750.3], 
                                    [-77542.44326698, -77542.44326698,-4114.32,-20925.9], 
                                    [25443.66844412, 25443.66844412 ,-34930.5,-32079.9], 
                                    [50667.36400485, 50667.36400485,-40446.8,-27178.3], 
                                    [-74279.50968878, -74279.50968878,-35130.2,-36423.6], 
                                    [24326.77955838, 24326.77955838,40040.3,38561.4], 
                                    [-4359.51,-4359.51 ,-4359.51,748.7], 
                                    [4359.51, 4359.51,4359.51,-748.7]])
    print("Icoil_ref_scenario : ", Icoil_ref_scenario)

    t_Icoils_ref_scenario=np.array([160.000,161.0,180.0,200.050])
    
    Icoil_ref_cur=np.copy(Icoil_ref_scenario[:,0])
    Icoil_ref_cur= np.reshape(Icoil_ref_cur, (np.shape(Icoil_ref_cur)[0],1) )
    
    Icoil_cur=np.copy(Icoil_ref_cur)

    err_Icoil_cur=Icoil_cur-Icoil_ref_cur
    
    ## Plasma position controller coefs initialisation
    Kp_rgeom=2.0e5
    Ki_rgeom=1.0e5
    Kp_zgeom=-1.0e4
    Ki_zgeom=-5.0e3
    Kp_ip=1.0e-1
    Ki_ip=5.0e-2
    
    #Mapping of the geometric axis and Ip control to corresponding PF coils
    B_map = np.array([[0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [1.0, 0.0, 0.0],
                     [1.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 0.0, 0.0],
                     [0.0, 1.0, 0.0],
                     [0.0, 0.0, 0.0]])
    
    dIcoil_ref_cur=np.zeros((3,1))
    
    Xi_rgeom_cur=0.0
    Xi_zgeom_cur=0.0
    Xi_ip_cur=0.0
    
    # Plasma position reference
    
    rgeom_ref_scenario=np.array([5.554,5.554, 5.554, 6.2052])
    zgeom_ref_scenario=np.array([-0.006,-0.006,-0.006, 0.2808])
    ip_ref_scenario=np.array([0.5e7,0.5e7, 1.0e7,1.0e7])

    t_position_ref_scenario=np.array([160.000,161.0, 180.0,200.050])

    rgeom_ref_cur=rgeom_ref_scenario[0]
    zgeom_ref_cur=zgeom_ref_scenario[0]
    ip_ref_cur=ip_ref_scenario[0]

    print(np.shape(rgeom_ref_cur))

    rgeom_cur=rgeom_ref_cur
    zgeom_cur=zgeom_ref_cur
    ip_cur=ip_ref_cur
    
    
    err_rgeom_cur=rgeom_cur-rgeom_ref_cur
    err_zgeom_cur=zgeom_cur-zgeom_ref_cur
    err_ip_cur=ip_cur-ip_ref_cur
    
  return values


def receive_ids(instance, ids_name, port_name):
    if not instance.is_connected(f"{ids_name}_{port_name}"):
        return
    msg = instance.receive(f"{ids_name}_{port_name}")
    t_cur = msg.timestamp
    t_next = msg.next_timestamp
    ids_data = getattr(IDSFactory(), ids_name)()
    ids_data.deserialize(msg.data)
    return ids_data, t_cur, t_next


def send_ids(instance, ids, ids_name, port_name):
    if not self.instance.is_connected(f"{ids_name}_{port_name}"):
        return
    msg = Message(ids.time[-1], data=ids.serialize())
    self.instance.send(f"{ids_name}_{port_name}", msg)


def init_pf_active_out():
  pf_active_out=imas.pf_active()
  pf_active_out.ids_properties.homogeneous_time=1    
  pf_active_out.time.resize(1)
  pf_active_out.supply.resize(14)
  return pf_active_out
           	

def apply_controller(equilibrium_ref, equilibrum, pf_active):
  pf_active_out = init_pf_active_out()
  values = get_values()
  values['rgeom']=equilibrium.time_slice[0].boundary.geometric_axis.r
  values['zgeom']=equilibrium.time_slice[0].boundary.geometric_axis.z
  values['ip']=np.abs(equilibrium.time_slice[0].global_quantities.ip)
  values['rgeom_ref']=equilibrium_ref.time_slice[0].boundary.geometric_axis.r
  values['zgeom_ref']=equilibrium_ref.time_slice[0].boundary.geometric_axis.z
  values['ip_ref']=np.abs(equilibrium_ref.time_slice[0].global_quantities.ip)
  values['err_rgeom'] = values['rgeom'] - values['rgeom_ref']
  values['err_zgeom'] = values['zgeom'] - values['zgeom_ref']
  values['err_ip'] = values['ip'] - values['ip_ref']
  values['dIcoil_ref'][0]=values['Kp_rgeom']*values['err_rgeom']+values['Ki_rgeom']*values['Xi_rgeom']
  values['dIcoil_ref'][1]=values['Kp_zgeom']*values['err_zgeom']+values['Ki_zgeom']*values['Xi_zgeom']
  values['dIcoil_ref'][2]=values['Kp_ip']*values['err_ip']+values['Ki_ip']*values['Xi_ip']
  values['Icoil_ref'] = get_Icoil_ref(pf_active_ref)

  for i in range(14):
      values['Icoil'][i]=pf_active.coil[i].current.data


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    MagneticController()
