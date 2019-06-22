def cluster_config(nodeNumber):
    cluster_config = f'''
set services rpm probe icmp-ping-probe test ping-probe-test probe-type icmp-ping
set services rpm probe icmp-ping-probe test ping-probe-test target address 8.8.4.4
set services rpm probe icmp-ping-probe test ping-probe-test probe-count 3
set services rpm probe icmp-ping-probe test ping-probe-test probe-interval 2
set services rpm probe icmp-ping-probe test ping-probe-test test-interval 15
set services rpm probe icmp-ping-probe test ping-probe-test history-size 50
set services rpm probe icmp-ping-probe test ping-probe-test thresholds successive-loss 4
set event-options policy ping-test-success events ping_test_completed
set event-options policy ping-test-success attributes-match ping_test_completed.test-owner matches icmp-ping-probe
set event-options policy ping-test-success attributes-match ping_test_completed.test-name matches ping-probe-test
set event-options policy ping-test-success then change-configuration commands "deactivate services rpm probe icmp-ping-probe test ping-probe-test"
set event-options policy ping-test-success then change-configuration commit-options log "Updating configuration from event policy"
set event-options policy ping-test-success then execute-commands commands "op url http://10.0.0.204/static/slax/chassis-cluster.slax node-id {nodeNumber}"
'''
    return cluster_config