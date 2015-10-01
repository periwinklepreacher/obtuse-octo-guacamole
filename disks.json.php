<?php
    $device = '(?P<device>[^\s]+)';
    $size = '(?P<size>[^\s]+)';
    $used = '(?P<used>[^\s]+)';
    $available = '(?P<available>[^\s]+)';
    $use = '(?P<use>[^\s]+)';
    $mount = '(?P<mount>[^\s]+)';
    $expression = '/'.$device.'\s*'.$size.'\s*'.$used.'\s*'.$available.'\s*'.$use.'\s*'.$mount.'/';
    exec( 'df -P', $output );

    $ln = array();
    foreach( $output as $line ) {
            preg_match( $expression, $line, $matches );
            if( $matches['device'] != '' && $matches['device'] != 'Filesystem' ) {
                    $df = array();
                    $df[] = "\"device\" : " . "\"" . $matches['device'] . "\"";
                    $df[] = "\"size\" : " . $matches['size'] . "";
                    $df[] = "\"used\" : " . $matches['used'] . "";
                    $df[] = "\"available\" : " . $matches['available'] . "";
                    $df[] = "\"use\" : " . "\"" . $matches['use'] . "\"";
                    $df[] = "\"mount\" : " . "\"" . $matches['mount'] . "\"";
                    $ln[] = "{" . implode(",", $df) . "}";
            }
    }
    print "[" . implode(",", $ln) . "]";
?>
