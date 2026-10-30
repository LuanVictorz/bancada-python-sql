# Publicar no GitHub

## Antes de enviar

1. Extraia o ZIP do projeto.
2. Execute `python main.py --demo` e confira a interface.
3. Execute `python -m unittest discover -s tests -v`.
4. Feche a aplicação.

Se você executou antes do envio, algumas pastas foram criadas. Publique apenas o conteúdo original do ZIP, sem `dados`, `__pycache__`, backups ou exportações. No envio pelo navegador, o `.gitignore` não remove arquivos da fila automaticamente.

## Pelo navegador

1. Entre no GitHub e abra [criar repositório](https://github.com/new).
2. Use o nome `bancada-python-sql`.
3. Descrição sugerida: `Gestão de manutenção com Python e SQLite: interface desktop, estoque, custos, relatórios e testes.`
4. Selecione **Public** e deixe desativada a criação de README, `.gitignore` e licença.
5. Clique em **Create repository**.
6. Na caixa **Quick setup**, clique em **uploading an existing file**.
7. Arraste os arquivos e subpastas de dentro de `bancada-python-sql` para a área de envio. O README deve ficar na raiz. Arraste as pastas pelo Explorador de Arquivos para manter sua estrutura.
8. Confira os arquivos. Não envie o ZIP nem a pasta externa inteira.
9. No primeiro campo de commit, escreva `Adiciona gestão de manutenção com Python e SQLite`.
10. Conclua em **Commit changes**.

O README deverá aparecer formatado abaixo dos arquivos. Em **About**, você pode adicionar os tópicos `python`, `sqlite`, `sql`, `tkinter`, `inventory` e `maintenance`.

Inclua também a pasta `.github`. Ela contém o fluxo para executar os testes no GitHub Actions em Windows e Linux. Depois do envio, acompanhe a aba **Actions**. A execução remota só poderá ser confirmada depois da publicação; os testes locais estão registrados na documentação. [Referência do fluxo Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).

Se o nome já existir na sua conta, não substitua outro projeto por engano. Abra o repositório existente se for este projeto ou escolha um nome novo.

## Atualizações

Para uma mudança pequena de documentação, abra o arquivo no GitHub, clique no lápis, edite e faça um commit. Para mudanças no código, prefira trabalhar em uma cópia local com Git, executar os testes e enviar o conjunto completo da alteração.

Você já tem projetos anteriores no perfil. Este pode ser apresentado como um projeto de estudo mais completo, com uma execução demonstrável e decisões de banco documentadas.

Referências: [criar repositório](https://docs.github.com/pt/repositories/creating-and-managing-repositories/creating-a-new-repository) e [enviar arquivos](https://docs.github.com/pt/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).
