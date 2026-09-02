import React, { useState } from "react";
import { Menu, Moon, Sun, FlaskConical } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function Topbar({ onMenuClick }) {
  const { theme, setTheme, lang, setLang, org, toggleTestMode, t } = useApp();
  const testMode = !!org?.test_mode;
  const [confirmOff, setConfirmOff] = useState(false);

  const onTestModeClick = () => {
    if (testMode) {
      setConfirmOff(true);
    } else {
      toggleTestMode().then(() => toast.success("Test Mode réactivé"));
    }
  };

  const confirmTurnOff = async () => {
    await toggleTestMode();
    setConfirmOff(false);
    toast.warning("Test Mode désactivé — les envois réels sont maintenant possibles");
  };

  return (
    <div className="sticky top-0 z-30 bg-background/80 backdrop-blur-md border-b border-border">
      {testMode && (
        <div
          data-testid="test-mode-banner"
          className="w-full bg-warning/10 border-b border-warning/30 px-4 py-1.5 text-xs flex items-center justify-center gap-2"
          style={{ color: "hsl(var(--warning))" }}
        >
          <FlaskConical className="w-3.5 h-3.5" />
          <span className="font-medium">{t("test_mode.banner")}</span>
        </div>
      )}
      <div className="h-14 px-4 lg:px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            data-testid="topbar-menu"
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-md hover:bg-accent"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="hidden lg:block text-xs text-muted-foreground mono">
            {new Date().toLocaleDateString(lang === "fr" ? "fr-CH" : "en-US", { weekday: "long", day: "numeric", month: "long" })}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <Button
            data-testid="topbar-testmode-toggle"
            variant={testMode ? "default" : "outline"}
            size="sm"
            onClick={onTestModeClick}
            className={cn("h-8 text-xs gap-1.5 hidden sm:inline-flex", testMode && "hover:opacity-90")}
            style={testMode ? { backgroundColor: "hsl(var(--warning))", color: "white" } : {}}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            {t("test_mode")}: {testMode ? "ON" : "OFF"}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button data-testid="topbar-lang" variant="ghost" size="sm" className="h-8 w-10 text-xs mono">
                {lang.toUpperCase()}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem data-testid="lang-fr" onClick={() => setLang("fr")}>Français</DropdownMenuItem>
              <DropdownMenuItem data-testid="lang-en" onClick={() => setLang("en")}>English</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            data-testid="topbar-theme"
            variant="ghost" size="icon"
            className="h-8 w-8"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      <AlertDialog open={confirmOff} onOpenChange={setConfirmOff}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver le Test Mode ?</AlertDialogTitle>
            <AlertDialogDescription>
              Une fois désactivé, Aura Hub peut envoyer de vrais messages et appeler
              les intégrations réelles (si configurées). Les protections de sécurité
              restent actives. Confirmer ?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction data-testid="confirm-test-mode-off" onClick={confirmTurnOff}>
              Désactiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
