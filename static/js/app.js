// Componentes Alpine (versão CSP: sem eval). Tudo funciona também sem JavaScript.
document.addEventListener("alpine:init", function () {
  // Teclado de valor em centavos: "4590" → "45,90" (ui-ux-specification.md §7, §10.2).
  Alpine.data("keypad", function () {
    return {
      digits: "",
      init: function () {
        var input = this.$refs.amount;
        if (input && input.value) this.digits = input.value.replace(/\D/g, "").replace(/^0+/, "");
        this.render();
      },
      press: function (event) {
        var key = event.currentTarget.dataset.key;
        if (key === "back") this.digits = this.digits.slice(0, -1);
        else if (this.digits.length < 11) this.digits = (this.digits + key).replace(/^0+/, "");
        this.render();
      },
      render: function () {
        var cents = this.digits.padStart(3, "0");
        var reais = cents.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        var text = reais + "," + cents.slice(-2);
        if (this.$refs.amount) this.$refs.amount.value = this.digits ? text : "";
        if (this.$refs.display) this.$refs.display.textContent = "R$ " + text;
      },
    };
  });

  // Mostra campos conforme o tipo (gasto, recebimento, transferência).
  Alpine.data("entryKind", function () {
    // Valores simples (não getters nem métodos): a versão CSP do Alpine só reage assim em x-show.
    return {
      kind: "expense",
      isExpense: true,
      isIncome: false,
      isTransfer: false,
      isCard: false,
      notCard: true,
      usesExpenseCategory: true,
      init: function () {
        var checked = this.$root.querySelector('input[name="kind"]:checked');
        this.sync(checked ? checked.value : "expense");
      },
      pick: function (event) {
        if (event.target && event.target.name === "kind") this.sync(event.target.value);
      },
      sync: function (kind) {
        this.kind = kind;
        this.isExpense = kind === "expense";
        this.isIncome = kind === "income";
        this.isTransfer = kind === "transfer";
        this.isCard = kind === "card";
        this.notCard = kind !== "card";
        this.usesExpenseCategory = kind === "expense" || kind === "card";
      },
    };
  });

  // Atalhos de data: hoje e ontem.
  Alpine.data("dateShortcuts", function () {
    return {
      set: function (event) {
        var offset = parseInt(event.currentTarget.dataset.offset, 10);
        var d = new Date();
        d.setDate(d.getDate() - offset);
        var iso = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" +
          String(d.getDate()).padStart(2, "0");
        this.$refs.date.value = iso;
      },
    };
  });

  // Tema claro, escuro ou automático, guardado neste aparelho.
  Alpine.data("themePicker", function () {
    return {
      choice: "auto",
      init: function () {
        try { this.choice = localStorage.getItem("fin-theme") || "auto"; } catch (e) {}
        var radio = this.$root.querySelector('input[value="' + this.choice + '"]');
        if (radio) radio.checked = true;
      },
      pick: function (event) {
        this.choice = event.target.value;
        try {
          if (this.choice === "auto") localStorage.removeItem("fin-theme");
          else localStorage.setItem("fin-theme", this.choice);
        } catch (e) {}
        if (this.choice === "auto") document.documentElement.removeAttribute("data-theme");
        else document.documentElement.setAttribute("data-theme", this.choice);
      },
    };
  });

  // Avisos somem sozinhos depois de alguns segundos.
  Alpine.data("toast", function () {
    return {
      open: true,
      init: function () {
        var self = this;
        var ms = parseInt(this.$root.dataset.timeout || "6000", 10);
        setTimeout(function () { self.open = false; }, ms);
      },
      close: function () { this.open = false; },
    };
  });
});

// Botões de envio ficam desabilitados durante o envio (evita duplo toque; RN-170 protege mesmo assim).
document.addEventListener("submit", function (event) {
  var form = event.target;
  window.setTimeout(function () {
    form.querySelectorAll("button[type=submit]").forEach(function (b) { b.disabled = true; });
  }, 0);
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
}
