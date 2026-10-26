.. _`writing_actors`:

Writing PDS actors
==================

This page assumes a working knowledge of MUSCLE3; if you do not have one, start with the
`MUSCLE3 documentation <https://muscle3.readthedocs.io/en/latest/>`__.

Optional ports
--------------

An actor may be a macro model, a micro model, or both, so declare every port it might use
on the instance at initialization -- that way the port is always available and the ymmsl
workflow decides whether to wire it. Guard each send and receive with
``instance.is_connected(port_name)``.

Propagate t_next
----------------

Put both the timestamp and the next timestamp on every outgoing message: downstream
actors use ``next_timestamp`` to bridge timescales and to decide when a loop stops. On the
last message set it to null, which signals that nothing follows. An actor with an inner
and an outer loop tracks one for each.

Port naming
-----------

Port names usually combine the IDS name with the MUSCLE3 operator --
``equilibrium_o_i``, ``core_profiles_f_init`` -- or, for an actor with a single port each
way, ``<ids_name>_in`` and ``<ids_name>_out``. Conventions vary between actors, so check
the one you are wiring against.

Example
-------

A generic Python actor for a fictional code ``MyModel``. It uses the ``equilibrium`` IDS
on all four operators, treats O_I and S as optional, and propagates the next timestamp.

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

      outer_t = eq_msg.timestamp

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
