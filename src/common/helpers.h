#ifndef _HELPERS_H_
#define _HELPERS_H_

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Read actions config update by user.
 * 
 * The LOM Service comes with pre-built config based on YANG schema
 * This includes attributes like enable/disable, timeout, hearbeat-interval, ...
 * User could tweak any of that.
 * This will be applied on pre-built static config
 *
 * Input:
 *  buf - Buffer to copy JSON string of the config objects.
 *  bufsz - Size of the buf
 *
 * Output:
 *  buf -
 *      Entire config as JSON string, if size is sufficient.
 *      If size not sufficient, no data is copied, but required
 *      size is written out.
 *      The write includes terminating null char.
 *        
 *  e.g.
 *      {
 *          <action name>: { <attr name>: <value>, ...},
 *          ...
 *      }
 *
 * Return:
 *  count of chars of final config string.
 *  If this <= bufsz, the string is copied into the giveb buf.
 *
 */
int get_LoM_Actions_config_tweaks(const char *buf, int bufsz);


/*
 * Read global config update by user.
 * 
 * The LOM Service comes with pre-built global config.
 *  
 * This includes attributes like enable/disable, heartbeat intervals,
 * max time for mitigation sequence, ...
 * User could tweak any of that.
 * This will be enforced at run time by LoM service,
 * The global config, where it pertains overrides action level config
 *
 * Input:
 *  buf - Buffer to copy JSON string of the config objects.
 *  bufsz - Size of the buf
 *
 * Output:
 *  buf -
 *      Entire config as JSON string, if size is sufficient.
 *      If size not sufficient, no data is copied, but required
 *      size is written out.
 *      The write includes terminating null char.
 *        
 *  e.g.
 *      {
 *          <action name>: { <attr name>: <value>, ...},
 *          ...
 *      }
 *
 * Return:
 *  count of chars of final config string.
 *  If this <= bufsz, the string is copied into the giveb buf.
 *
 */
int get_LoM_global_config_tweaks(const char *buf, int bufsz);


/*
 * Write current running actions config for visibility to end users/tools
 *
 * e.g. SONiC can write into STATE-DB. Expose via CLI & gNMI.
 *
 * Input:
 *  buf -
 *      JSON string of all actions.
 *      This could be written into some DB per schema (DB-Actions.yang)
 *      for visibiility
 *
 * Output:
 *      None
 *
 * Return:
 *  0 - Success
 *  !=0 implies failure.
 */
int set_LoM_actions_config(const char *cfg);


/*
 * Write current global running config for visibility to end users/tools
 *
 * e.g. SONiC can write into STATE-DB. Expose via CLI & gNMI.
 *
 * Input:
 *  buf -
 *      JSON string of all actions.
 *      This could be written into some DB per schema (DB-Actions.yang)
 *      for visibiility
 *
 * Output:
 *      None
 *
 * Return:
 *  0 - Success
 *  !=0 implies failure.
 */
int set_LoM_global_config(const char *cfg);


/*
 * Set Action state
 *
 * Sets the status of the action
 *
 * Input:
 *  action-name - Name of the action
 *  status-date - JSON string of key/val for a subset of attributes
 *
 * Output:
 *  None
 *
 * Return:
 *  0 - Success
 *  !=0 implies failure.
 */
int set_LoM_actions_state(const char *action_name, const char *status);

#ifdef __cplusplus
}
#endif


#endif // _HELPERS_H_
