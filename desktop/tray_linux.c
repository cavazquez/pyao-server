/* ProyectoAO native Linux tray bridge, MIT. No server or game state lives here. */
#include <gtk/gtk.h>
#include <libayatana-appindicator/app-indicator.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static AppIndicator *indicator;
static GtkWidget *state_item;
static GtkWidget *stop_item;
static gboolean connected = FALSE;

static void emit(const char *event) { puts(event); fflush(stdout); }

static void action(GtkMenuItem *item, gpointer event) {
    (void)item;
    emit((const char *)event);
    if (strcmp(event, "DETACH") == 0) gtk_main_quit();
}

static GtkWidget *entry(GtkWidget *menu, const char *label, const char *event) {
    GtkWidget *item = gtk_menu_item_new_with_label(label);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
    g_signal_connect(item, "activate", G_CALLBACK(action), (gpointer)event);
    return item;
}

static void connection_changed(AppIndicator *source, gboolean value, gpointer unused) {
    (void)source; (void)unused;
    connected = value;
    emit(value ? "READY" : "UNAVAILABLE");
}

static gboolean check_host(gpointer unused) {
    (void)unused;
    if (!connected) { emit("UNAVAILABLE"); gtk_main_quit(); }
    return G_SOURCE_REMOVE;
}

static gboolean input(GIOChannel *channel, GIOCondition condition, gpointer unused) {
    (void)unused;
    if (condition & (G_IO_HUP | G_IO_ERR)) { gtk_main_quit(); return G_SOURCE_REMOVE; }
    gchar *line = NULL;
    GIOStatus status = g_io_channel_read_line(channel, &line, NULL, NULL, NULL);
    if (status == G_IO_STATUS_EOF) { gtk_main_quit(); return G_SOURCE_REMOVE; }
    if (status != G_IO_STATUS_NORMAL) return G_SOURCE_CONTINUE;
    g_strchomp(line);
    if (g_str_has_prefix(line, "TITLE ")) {
        app_indicator_set_title(indicator, line + 6);
        gtk_menu_item_set_label(GTK_MENU_ITEM(state_item), line + 6);
    } else if (strcmp(line, "STOPPED") == 0 && stop_item) {
        gtk_widget_set_sensitive(stop_item, FALSE);
    } else if (strcmp(line, "QUIT") == 0) {
        g_free(line); gtk_main_quit(); return G_SOURCE_REMOVE;
    }
    g_free(line);
    return G_SOURCE_CONTINUE;
}

int main(int argc, char **argv) {
    if (argc != 4) { fputs("usage: pyao-tray client|server icon-path title\n", stderr); return 2; }
    const gboolean server = strcmp(argv[1], "server") == 0;
    if (!server && strcmp(argv[1], "client") != 0) return 2;
    if (!gtk_init_check(NULL, NULL)) { emit("UNAVAILABLE"); return 0; }
    gchar *name = g_strdup_printf("pyao-%s-%ld", argv[1], (long)getpid());
    /* GTK3/Ayatana is the bridge API shipped by Ubuntu core24/core26. */
    G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    indicator = app_indicator_new(name, argv[2], APP_INDICATOR_CATEGORY_APPLICATION_STATUS);
    G_GNUC_END_IGNORE_DEPRECATIONS
    g_free(name);
    app_indicator_set_title(indicator, argv[3]);
    GtkWidget *menu = gtk_menu_new();
    state_item = gtk_menu_item_new_with_label(argv[3]);
    gtk_widget_set_sensitive(state_item, FALSE);
    gtk_menu_shell_append(GTK_MENU_SHELL(menu), state_item);
    if (server) {
        entry(menu, "Ver registros", "LOGS");
        stop_item = entry(menu, "Detener servidor", "STOP");
        entry(menu, "Cerrar indicador", "DETACH");
    } else {
        entry(menu, "Mostrar cliente", "SHOW");
        entry(menu, "Salir del cliente", "EXIT");
    }
    gtk_widget_show_all(menu);
    app_indicator_set_menu(indicator, GTK_MENU(menu));
    g_signal_connect(indicator, "connection-changed", G_CALLBACK(connection_changed), NULL);
    app_indicator_set_status(indicator, APP_INDICATOR_STATUS_ACTIVE);
    GIOChannel *channel = g_io_channel_unix_new(STDIN_FILENO);
    g_io_channel_set_flags(channel, G_IO_FLAG_NONBLOCK, NULL);
    g_io_add_watch(channel, G_IO_IN | G_IO_HUP | G_IO_ERR, input, NULL);
    g_timeout_add_seconds(5, check_host, NULL);
    gtk_main();
    app_indicator_set_status(indicator, APP_INDICATOR_STATUS_PASSIVE);
    g_io_channel_unref(channel);
    gtk_widget_destroy(menu);
    g_object_unref(indicator);
    return 0;
}
