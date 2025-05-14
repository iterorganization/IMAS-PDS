.. _`writing_actors`:

Writing PDS actors
==================

Here we provide an explanation for how to write MUSCLE3 actors
within the PDS ecosystem.

MUSCLE3
-------

Since the PDS actors are based on the MUSCLE3 framework,  
it is recommended to look at the
`MUSCLE3 documentation <https://muscle3.readthedocs.io/en/latest/>`__
to get a good understanding of the basics. The rest of this page is
written with the assumption that the reader has a basic understanding
of the MUSCLE3 framework.

Inner/outer loop structure
--------------------------

MUSCLE3 actors might work as a macro model, a micro model, or both
at the same time. Make sure that the actor is connected on any port
it might use within the PDS ecosystem.
When a certain port is optional in your actor, you can simple add it to your
muscle instance on its initialization so that the port is always available.
However, make sure it only send or receive when the port is connected in
the ymmsl workflow (check with ``instance.is_connected(port_name)``).

Propagate t_next
----------------

Some actors need to be able to see what the next timestamp will be.
This information can be used to set up a timescale bridge between
actors or for the stopping condition of a loop. Try to make sure
that both the timestamp and next timestamp
are added to any outgoing muscle message.
If it is the last message, set next_timestamp to None/nil/null/etc.
to signal that will be no more messages coming after it.
A seperate next_timestamp might be tracked for
the outer and inner loop of the actor.

Optional timescale bridge
-------------------------

TODO

Conventions
-----------

Port names generally have a structure where they combine the ids_name
with the muscle3 port on which it receives or sends messages
("equilibrium_o_i", "core_profiles_f_init").
Another common structure is ``<ids_name>_in`` and ``<ids_name>_out``
if you only use 1 outgoing and/or 1 ingoing port.
However these names might differ between actors so do check
the documentation of the actor you are using.

PDS actor example
-----------------

To provide an example, underneath is the code for what a generic PDS
muscle3 actor in python would look like for the fictional simulation code 'MyModel'.
The actor can use the equilibrium IDS on all ports,
but the O_I and S ports are optional 
and the actor won't use them if they are not connected.
It propagates the next timestamp so that any connected actor
that needs it is able to use it.

.. code-block:: python

  """
  MUSCLE3 actor example
  """

  import logging

  import imas
  from libmuscle import Instance, Message
  from ymmsl import Operator

  from my_model import MyModel

  logger = logging.getLogger()

  def main():
    """Actor main function"""
    # Initialize MUSCLE3 instance with both mandatory and optional ports
    instance = Instance(
      {
        Operator.F_INIT: ["equilibrium_f_init"],
        Operator.O_I: ["equilibrium_o_i"], # optional port
        Operator.S: ["equilibrium_s"], # optional port
        Operator.O_F: ["equilibrium_o_f"],
      }
    )
    # Initialize model outside reuse_instance loop
    model = MyModel()
    factory = imas.IDSFactory()
    while instance.reuse_instance():
      # F_INIT
      dt = instance.get_setting('dt')
      n_timesteps = instance.get_setting('n_timesteps')

      eq_msg = instance.receive("equilibrium_f_init")
      eq_ids = factory.new("equilibrium")
      eq_ids.deserialize(eq_msg.data)

      outer_t = eq_msg.t_timestamp

      # make sure we keep track of t_next in outer loop
      outer_t_next = eq_msg.next_timestamp

      for i in range(n_timesteps):
        # O_I
        inner_t = outer_t + i * dt
        # make sure we send out t_next in inner loop
        if i == n_timesteps - 1:
          inner_t_next = None
        else:
          inner_t_next = inner_t + dt
        # only send optional port if connected in ymmsl file
        if instance.is_connected("equilibrium_o_i"):
          msg_out = Message(inner_t, next_timestamp=inner_t_next, data=eq_ids.serialize())
          instance.send("equilibrium_o_i", msg_out)

        # S
        # only receive optional port if connected in ymmsl file
        if instance.is_connected("equilibrium_s"):
          eq_msg = instance.receive("equilibrium_s")
          eq_ids = factory.new("equilibrium")
          eq_ids.deserialize(eq_msg.data)

        # run single timestep of model with the updated equilibrium data
        eq_ids = model.run_timestep(eq_ids)

      # O_F
      msg_out = Message(outer_t, next_timestamp=outer_t_next, data=eq_ids.serialize())
      instance.send("equilibrium_o_f", msg_out)

    # do any cleanup your code needs to do after the reuse_instance loop
    model = MyModel()

  if __name__ == "__main__":
    logging.basicConfig(
      format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
      level=logging.INFO,
    )
    main()


Documenting PDS actors
======================

Here we provide the general outline for documentation of PDS actors.
Some examples are provided `here <https://confluence.iter.org/display/IMP/PDS+Muscle3+Actors>`__.

Actor Summary
-------------

Summary of what the actor does and what it can be used for.

Optional: available operational modes
-------------------------------------

If the actor has multiple operational modes, introduce them here and
show how these different modes are implemented.

Available Settings
------------------

Show any settings that the actor uses. Often divided in a mandatory
section and an optional section. 
For each setting show:

* Name
* Data type
* Mandatory/optional
* Relevant for which operation modes
* Explanation of effect
* Default value if optional

Available Ports
---------------

Show all the available ports for your actor.
Often divided in a mandatory section and an optional section.
Can also be divided into subsections per operator.
For each port show:

* Name
* Port (f_init, o_i, s, o_f)
* Mandatory/optional
* Relevant for which operational modes
* Explanation
* Default behavior if optional

Required input/output fields per IDS
------------------------------------

Document which fields per IDS are required as input for this actor
and which fields are available in the output.
This is necessary to check the compatibility of different actors.

General Info
------------

Any other information that might be useful.
(For example, compatible Data Dictionary versions)
