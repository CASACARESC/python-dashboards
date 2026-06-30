# python-dashboards

Repositório dos dashboards Python da intranet Casa Caresc.

---

## Como começar

### 1. Instalar o Git

Baixar em https://git-scm.com/download/win e instalar com as opções padrão.

### 2. Clonar o repositório

```bash
git clone https://github.com/CASACARESC/python-dashboards.git
```

### 3. Estrutura de pastas

Cada dashboard fica em sua própria pasta:

```
python-dashboards/
├── nome-do-dashboard/
│   ├── index.html        ← arquivo principal
│   └── (assets opcionais)
└── outro-dashboard/
    └── index.html
```

### 4. Testar

Abra o `index.html` do dashboard direto no navegador — não precisa de servidor, PHP ou qualquer outra instalação.

---

## Como salvar e enviar alterações

```bash
# 1. Entrar na pasta do projeto
cd python-dashboards

# 2. Verificar o que mudou
git status

# 3. Adicionar os arquivos alterados
git add .

# 4. Criar o commit com uma descrição do que foi feito
git commit -m "feat: adicionar dashboard de sinistros"

# 5. Enviar para o GitHub
git push
```

---

## Dicas

- Sempre crie uma pasta separada para cada dashboard
- Use nomes em minúsculas sem espaços (ex: `sinistros`, `producao-mensal`)
- O arquivo principal de cada dashboard deve se chamar `index.html`
