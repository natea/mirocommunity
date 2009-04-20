/* TODO: Allow and adjust for padding */

function remove_video_and_refresh_list(video_div) {
    video_div.fadeOut(1000, function() {video_div.remove()});
}

function run_and_disappear(eventdata) {
    var this_anchor = $(this);
    var video_div = this_anchor.parent().parent();
    console.log(this_anchor.attr('href'));
    jQuery.ajax({
        url: this_anchor.attr('href'),
        success: function() {
            remove_video_and_refresh_list(video_div);}});
    return false;
}

function get_current_video_id() {
    return $('div.selected span.video_id').text();
}

function load_video(eventdata) {
    var viddiv = $(eventdata.currentTarget);
    var video_id = $('span.video_id', viddiv).text();
    var video_url = '/admin/preview_video/?video_id=' + video_id;
    var admin_rightpane = $('#admin_rightpane');
    jQuery.ajax({
            url: video_url,
            success: function(data) {
                admin_rightpane.empty().append(data);
                var selected = $('div.selected');
                selected.removeClass('selected');
                selected.addClass('unselected');
                selected.bind('click', load_video);
                selected.css('cursor', 'pointer');
                viddiv.removeClass('unselected');
                viddiv.addClass('selected');
                viddiv.unbind('click', load_video);
                viddiv.css('cursor', 'default');
                }});
}

function load_click_callbacks() {
    $('div.unselected').bind('click', load_video);
    $('div.video .approve_reject .approve').click(
        run_and_disappear);
    $('div.video .approve_reject .reject').click(
        run_and_disappear);
}

function resize_admin() {
    var header = document.getElementById('header');
    var admin_leftpane = document.getElementById('admin_leftpane');
    var admin_rightpane = document.getElementById('admin_rightpane');
    admin_leftpane.style.height = (window.innerHeight
                                   - header.clientHeight - 15) + "px";
    admin_rightpane.style.height = admin_leftpane.style.height;
}

if ('attachEvent' in window) {
    window.attachEvent('onload', resize_admin);
    window.attachEvent('onload', load_click_callbacks);
    window.attachEvent('onresize', resize_admin);
}
else {
    window.addEventListener('load', resize_admin, false);
    window.addEventListener('load', load_click_callbacks, false);
}
window.addEventListener('resize', resize_admin, false);
