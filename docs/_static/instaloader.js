$(function () {
    $('[data-toggle="tooltip"]').tooltip();

    $('.doc-sidebar > ul > li.current').attr("id", "localtoc");
    $('#localtoc ul').addClass("nav flex-column");
    $('#localtoc ul li').addClass("nav-item");
    $('#localtoc ul li a').addClass("nav-link");
    $('.doc-content').scrollspy({target: '#localtoc'});

    const top_href = '#' + $('.section:first').attr("id");
    $('#localtoc > a.current').attr("href", top_href);

    $('#navbarToc a').on("click", function () {
        const href = $(this).attr("href");
        if (href === '#') {
            window.location.href = top_href;
        } else {
            window.location.href = href;
        }
        $('#navbarToc').modal('hide');
    });
});