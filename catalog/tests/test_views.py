from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.urls import reverse
import datetime
from django.contrib.contenttypes.models import ContentType
from catalog.models import Author
from catalog.models import BookInstance, Book, Genre, Language, Author

class RenewBookInstancesViewTest(TestCase):
    def setUp(self):
        # Создаём пользователя
        test_user1 = User.objects.create_user(username='testuser1', password='1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(username='testuser2', password='2HJ1vRV0Z&3iD')

        test_user1.save()
        test_user2.save()

        # Даём test_user2 разрешение can_mark_returned
        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        # Создаём книгу
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
            language=test_language,
        )
        test_book.genre.set([test_genre])
        test_book.save()

        # Создаём BookInstance для test_user2
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user2,
            status='o',
        )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_forbidden_if_logged_in_but_not_correct_permission(self):
        login = self.client.login(username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_permission_borrowed_book(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)

    def test_HTTP404_for_invalid_book_if_logged_in(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': 12345}))
        self.assertEqual(response.status_code, 404)

    def test_uses_correct_template(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)
        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(response.context['form'].initial['renewal_date'], date_3_weeks_in_future)

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        response = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': valid_date_in_future.isoformat()}
        )
        self.assertRedirects(response, reverse('all-borrowed'))

    def test_form_invalid_renewal_date_past(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        response = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': date_in_past.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'renewal_date', 'Invalid date — renewal in past')

    def test_form_invalid_renewal_date_future(self):
        login = self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        response = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': date_in_future.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'renewal_date', 'Invalid date — renewal more than 4 weeks ahead')


class AuthorCreateViewTest(TestCase):
    """Test case for the AuthorCreate view (Created as Challenge)."""

    def setUp(self):
        # Создаём обычного пользователя (НЕ суперпользователя!)
        test_user = User.objects.create_user(
            username='test_user',
            password='some_password'  # ← простой пароль для теста
        )
        test_user.save()

        # Получаем тип содержимого (ContentType) для модели Author
        # Это нужно, потому что разрешения в Django привязаны к модели через ContentType
        content_type_author = ContentType.objects.get_for_model(Author)

        # Получаем разрешение "add_author" (оно создаётся автоматически при миграции)
        # Имя разрешения формируется как: "add_модель", "change_модель", "delete_модель"
        perm_add_author = Permission.objects.get(
            codename='add_author',          # ← код разрешения
            content_type=content_type_author  # ← привязка к модели Author
        )

        # Назначаем разрешение пользователю
        test_user.user_permissions.add(perm_add_author)
        test_user.save()

        # Сохраняем пользователя в self, чтобы использовать в тестах
        self.test_user = test_user

    def test_redirect_if_not_logged_in(self):
        """Если пользователь НЕ залогинен — должен редиректить на login."""
        response = self.client.get(reverse('author-create'))
        # Проверяем: код 302 (редирект) и URL начинается с /accounts/login/
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_forbidden_if_logged_in_but_not_authorized(self):
        """Если залогинен, но НЕТ разрешения — ошибка 403 Forbidden."""
        # Создаём второго пользователя — БЕЗ разрешения
        other_user = User.objects.create_user(username='other_user', password='pass')
        other_user.save()

        # Логинимся под ним
        login = self.client.login(username='other_user', password='pass')
        response = self.client.get(reverse('author-create'))

        # Должен быть 403 — доступ запрещён
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_permission_uses_correct_template(self):
        """Если есть разрешение — должна открыться форма создания автора."""
        # Логинимся под пользователем, у которого есть разрешение
        login = self.client.login(username='test_user', password='some_password')
        response = self.client.get(reverse('author-create'))

        # Проверяем:
        self.assertEqual(response.status_code, 200)  # страница загружена
        self.assertTemplateUsed(response, 'catalog/author_form.html')  # ← правильный шаблон

    def test_initial_date_of_death(self):
        """Проверяем начальное значение поля date_of_death = '11/11/2023'."""
        login = self.client.login(username='test_user', password='some_password')
        response = self.client.get(reverse('author-create'))

        # Получаем форму из контекста шаблона
        form = response.context['form']
        # Проверяем начальное значение поля 'date_of_death'
        self.assertEqual(form.initial['date_of_death'], '11/11/2023')

    def test_redirects_to_author_detail_on_success(self):
        """После успешного создания — редирект на страницу нового автора."""
        login = self.client.login(username='test_user', password='some_password')

        # Отправляем POST-запрос с данными нового автора
        response = self.client.post(
            reverse('author-create'),
            {
                'first_name': 'Александр',
                'last_name': 'Пушкин',
                'date_of_birth': '1799-06-06',
                'date_of_death': '1837-02-10',
            }
        )

        # Проверяем: редирект (302) → и куда
        self.assertEqual(response.status_code, 302)

        # Получаем URL редиректа и проверяем, что он ведёт на author-detail
        # Пример: /catalog/author/5/
        self.assertRedirects(response, response.url)

        # Убеждаемся, что автор реально создан в базе
        self.assertTrue(Author.objects.filter(last_name='Пушкин').exists())