var socket = io.connect('http://' + document.domain + ':' + location.port);
console.log('http://' + document.domain + ':' + location.port);
socket.on('connect', function() {
});

function render_template() {
var div = document.getElementById("rendered_template");
div.style.display = "block";
}

function display_form() {
var div = document.getElementById("form_div");
div.style.display = "block";
}

function display_answers() {
var div = document.getElementById("answers_div");
div.style.display = "block";
}

function display_console() {
var div = document.getElementById("console_div");
div.style.display = "block";
}

function display_git_console() {
var div = document.getElementById("git_console_div");
div.style.display = "block";
}

function update_big() {
var updated_answers = document.getElementById("dynamic_af").value;
$("#dynamic_af_large").val(updated_answers);
}

function update_small() {
var updated_answers = document.getElementById("dynamic_af_large").value;
$("#dynamic_af").val(updated_answers);
}

function gitlabPush() {
// Gather data needed to push to repo
var clientID = document.getElementById("clientID").value;
var repo_auth_token = document.getElementById("gitlabToken").value;
var node0serialNumber = document.getElementById("node0serialNumber").value;
var node1serialNumber = document.getElementById("node1serialNumber").value;
var device_config = document.getElementById("complete").value;
var repo_uri = document.getElementById("configRepo").value;
var ztp = document.getElementById("ztp").checked;
var cluster = document.getElementById("cluster").checked;
var dict = {'repo_uri': repo_uri, 'clientID': clientID, 'ztp': ztp, 'cluster': cluster, 'repo_auth_token': repo_auth_token, 'serialNumber': {'node0serialNumber': node0serialNumber, 'node1serialNumber': node1serialNumber}, 'device_config': device_config};
//alert(JSON.stringify(dict));

socket.emit('gitlabPush', JSON.stringify(dict));
}

function toggle_render_button() {
var div = document.getElementById("render_button");
div.style.display = "block";
}

function disconnect_repo() {
//document.getElementById("changerepo").value="";
location.reload();
}

function button_change(){
$('#action').html('Connect');
}

// SOCKET

socket.on('repoContent', function(msg) {
    //var msg = JSON.stringify(msg, null, 4)
    // console.log(msg);

    var text = "";

    for (var x in msg['files']) {
        text += '<option value=' + msg['files'][x] + '>' + x + '</option>\n';
    };

    // console.log(text);

    $("#template").html('<select class="form-control" name="templatefile" id="template" required>\n'+
    '<option disabled selected>Select a template...</option>\n' +
    text +
    '</select>');

    $('#repo_help').html(
    '<button id="action" type="button" class="btn btn-secondary btn-lg btn-block" onclick="location.reload()"">Disconnect</button>'

    );
    $("#template").attr("disabled",false);
    display_form();


});

socket.on('render_output', function(msg) {
    //console.log(msg);
    $('#post_process').html('');
    $("#complete").val(msg);
});

socket.on('console', function(msg) {
    //console.log(msg);
    var debug_log = document.getElementById("console");
    debug_log.value += ('[' + msg['event_time'] + ']: ' + Object.values(msg['event']) + '\n');
    debug_log.scrollTop = debug_log.scrollHeight;
});

socket.on('git_console', function(msg) {
    display_git_console();
    //console.log(msg);
    var git_debug_log = document.getElementById("git_console");
    git_debug_log.value += ('[' + msg['event_time'] + ']: ' + msg['event'] + '\n');
    git_debug_log.scrollTop = git_debug_log.scrollHeight;
});

// END

      // Once repo URL is provided, create a dynamic list of .j2 files in repo and display.

      function change_repo() {
      $('#action').html('Connecting...');

      var selected_repo = document.getElementById("selected_repo").options[document.getElementById('selected_repo').selectedIndex].text;
      var github_user = document.getElementById("github_user").value;
      var userRepos = {"selected_repo":selected_repo,"github_user":github_user};
      
      socket.emit('getRepo', {"data": JSON.stringify(userRepos)})

      // Sending user data to website console
      // socket.emit('console', {'event': userRepos});

      // Display the website console
      // display_console();

      //$("#changerepo").attr("disabled",true);

      };


// Function to dynamically load answer file onto page.

$(function() {
    $("select[name=templatefile]").change(function() {
    //$('#pre_answers').html('<img src="static/sm_loading.gif" /> retrieving...</img>');

    var dict = [];
    dict.push({
    key:   document.getElementById("template").name,
    value: document.getElementById("template").value
    });

    $("#view_template").html('<a href="' + document.getElementById("template").value + '" target="_blank"> (view template)</a>');

       $.ajax({
            url: "/show",
            type: "POST",
            contentType: 'application/json',
            data : JSON.stringify(dict),
            // async: false,

            // If answer file is found, update the page.
            success: function(response){
                    var text = document.querySelectorAll("#dynamic_af, #dynamic_af_large");
                    text.forEach(function(userItem) {
                    $(userItem).attr("disabled",false);
                    $(userItem).val(response);
                    });
                    //$("#dynamic_af").attr("disabled",false);
                    //$("#dynamic_af").val(response);
                    display_answers();
                    $('#pre_answers').html('');
                    toggle_render_button();
                }
       });
    });
});

// Function to take provided answers, and produce the final render.

$(function() {
    $("button[name=process]").click(
      function() {
        $('#post_process').html('<img src="static/sm_loading.gif" /> Rendering...</img>');
        var selected = document.getElementById("selected_repo");
        var template = document.getElementById("template").value;
        var sel_template = document.getElementById("template");
        var answers = document.getElementById("dynamic_af").value;
        var selected = document.getElementById("selected_repo");
        var selected_template = sel_template.options[sel_template.selectedIndex].text;
        var selected_repo = selected.options[selected.selectedIndex].text;
        var repo_url = selected.options[selected.selectedIndex].value;

        var data = {"selected_repo":selected_repo,"repo_url":repo_url,"template":template,"answers":answers, "selected_template":selected_template};
        async: false;


        socket.emit('console', {'event': ['rendering...']});
        socket.emit('render_template', {"data": JSON.stringify(data)});

    });
});

function copy() {
  let copy_render = document.getElementById("complete");
  copy_render.select();
  document.execCommand("copy");
};
