# Vértice CRM

## Idioma
Sempre responda em português brasileiro. Seja direto e objetivo.

## Sobre o projeto
CRM próprio da Vértice Agência Digital para gerenciar clientes, pipeline de vendas e controle financeiro.

- **URL:** https://verticeiapoa-cpu.github.io/vertice-crm/
- **Repositório:** github.com/verticeiapoa-cpu/vertice-crm
- **Tecnologia:** HTML, CSS, JavaScript puro (sem frameworks)
- **Armazenamento:** localStorage do navegador

## Funcionalidades existentes
- Dashboard com métricas (receita do mês, projetos ativos, a receber, total clientes)
- Pipeline de vendas com status: Prospect → Proposta → Fechado → Entregue
- Cadastro de clientes com pacote, valor, prazo, pagamento e observações
- Controle financeiro com meta mensal (R$ 2.800) e exportação Excel
- Modal de novo cliente e edição

## Pacotes disponíveis
- Landing Page Essencial · R$ 350
- Site Completo Profissional · R$ 550
- Site + Google Premium · R$ 750
- Agenda Online · sob consulta
- Controle de Clientes · sob consulta
- Catálogo Digital · sob consulta
- Painel Administrativo · sob consulta
- Pacote Completo · sob consulta

## Segmentos atendidos
Clínica de Estética, Salão de Beleza, Barbearia, Esmalteria, Micropigmentação, Designer de Sobrancelhas, Depilação, Massoterapia/Spa, Nutrição, Psicologia, Personal Trainer, Outros

## Padrões de código
- JavaScript vanilla, sem dependências externas
- Estilo visual: dark, amarelo (#f5c518) como cor de destaque
- Nomenclatura em português para variáveis e funções quando possível
- Comentários em português

## Instruções para o Claude Code
- Antes de alterar qualquer funcionalidade, explique o que vai mudar e aguarde confirmação
- Sempre teste a lógica de localStorage ao adicionar/editar dados
- Mantenha compatibilidade com os dados já salvos no navegador
- Ao adicionar campos novos, verifique se quebra dados antigos
