# Usar o Bancada

## Abrir a demonstração

1. Extraia o ZIP em uma pasta do computador.
2. Abra o PowerShell nessa pasta e confira `python --version`.
3. Execute `python main.py --demo`.
4. A janela mostra que está em modo de demonstração. Os nomes e registros são fictícios.

Se o Windows não encontrar Python, instale-o pelo [site oficial](https://www.python.org/downloads/windows/) e marque a opção de adicioná-lo ao PATH. Reabra o terminal depois da instalação. Use `python -m tkinter` para verificar se o suporte à interface está disponível. Em algumas distribuições Linux, o pacote de Tkinter é instalado separadamente.

Não é preciso executar scripts SQL manualmente para abrir a aplicação. A estrutura é criada e versionada pelo programa.

## Experimentar um atendimento

1. Abra **Equipamentos** e escolha um dos equipamentos cadastrados.
2. Em **Ordens**, crie uma ordem descrevendo um problema fictício. Escolha uma prioridade.
3. Abra o detalhe da ordem e inicie o atendimento com um técnico.
4. Acrescente uma anotação de diagnóstico.
5. Registre uma peça utilizada, com quantidade disponível no estoque.
6. Confira a peça e o custo no detalhe. Em **Estoque**, o saldo já deve ter diminuído.
7. Conclua a ordem, descrevendo a solução e, se necessário, informando o custo de mão de obra.
8. Volte à visão geral para consultar os indicadores. Feche e abra novamente para conferir a persistência.

A ordem passa por aberta, em andamento e concluída. Uma ordem encerrada não pode receber peças ou notas novas nesta versão.

## Devolver uma peça ou cancelar

Uma peça registrada por engano pode ser devolvida enquanto o atendimento está em andamento. A devolução é da linha inteira de consumo e só pode acontecer uma vez. O saldo retorna ao estoque e o custo dessa linha deixa de compor a ordem.

Para cancelar, informe um motivo. Se houver peças ainda consumidas, devolva-as antes. Isso evita um cancelamento que silenciosamente devolva ao estoque uma peça que já foi usada.

## Estoque e custos

Uma peça nova começa com saldo zero. Use a entrada de estoque para informar quantidade, custo unitário e observação.

O custo unitário da última entrada vira o custo de referência para novos consumos. Cada consumo guarda uma cópia desse valor. O projeto não calcula custo médio, FIFO, impostos ou valorização contábil de estoque.

O alerta de reposição aparece quando o saldo é menor ou igual ao mínimo cadastrado. É um indicador, sem pedido de compra automático.

## Prazos

As metas da versão atual são 24 horas para prioridade alta, 72 para média e 168 para baixa, contadas da abertura. São valores de estudo, não contratos de SLA de uma empresa.

A ordem pendente fica atrasada quando passa do prazo. As datas são armazenadas em UTC. O cálculo inclui noites, fins de semana e feriados.

## Base vazia

Execute `python main.py` sem o argumento de demonstração. Cadastre um equipamento e um técnico. Para utilizar peças, cadastre-as e registre uma entrada de estoque. Depois abra a primeira ordem.

A base normal é `dados/bancada.sqlite3`; a demonstração é `dados/demo.sqlite3`. Mover a pasta inteira do projeto move os bancos junto. Não envie essas bases ao GitHub.

## Exportação e backup

O botão de exportação salva as ordens em CSV, usando ponto e vírgula e UTF-8 com BOM. Os dados textuais recebem proteção contra interpretação como fórmula por planilhas. O arquivo representa os dados no momento da exportação.

O backup usa a API do SQLite para copiar uma base consistente, incluindo alterações confirmadas. Escolha um nome novo. O programa não substitui um arquivo que já existe.

Para abrir uma cópia sem substituir a base principal:

```powershell
python main.py --db "C:\caminho\para\copia.sqlite3"
```

O arquivo aberto se torna a base de trabalho dessa execução, portanto novas operações serão salvas nele. Preserve uma cópia original antes de testar uma recuperação. Use `--check` junto de `--db` para conferir a cópia sem abrir a interface.

## O que esta versão não cobre

Uso simultâneo por uma equipe em rede, permissões por usuário, criptografia, anexos, sincronização, faturamento, horas úteis, edição de ordens encerradas e devolução parcial de uma linha não fazem parte da versão atual. O SQLite serializa as gravações locais, mas isso não transforma o programa em um sistema para várias estações de trabalho.
