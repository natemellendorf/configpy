$(document).ready(function(){
    //connect to the socket server.
    var socket = io.connect('http://' + document.domain + ':' + location.port);
    socket.on('connect', function() {
    //receive details from server
    socket.on('create', function(msg) {
        $('#log').html(msg['updates']);
    });

});